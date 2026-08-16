"""Tests for the 4 Field IoT Agent read tools (roadmap M1.4) — called
directly, no LLM involved (that wiring is M2). Checks output shape against
the examples in docs/agent-core/02-agents-and-tools.md C.2.1-C.2.4, plus at
least one error case per tool."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from agent_core.evidence.ledger import EvidenceLedger
from agent_core.state.store import FarmStateStore
from agent_core.tools.field_iot import (
    get_anomaly_report,
    get_device_snapshot,
    get_freshness_report,
    get_metric_series,
)


@pytest.fixture
def settings():
    return SimpleNamespace(freshness_fresh_sec=60, freshness_stale_sec=600)


@pytest.fixture
def store(tmp_path):
    return FarmStateStore(db_path=tmp_path / "farm_state.db")


@pytest.fixture
def ledger():
    return EvidenceLedger()


def _raw(device_id: str, t: float, **metrics) -> dict:
    return {"device_id": device_id, "timestamp": t, "event_time": t, **metrics}


def _window(device_id: str, t: float, metrics_avg: dict, *, anomalies=None, window_type="SLIDING_10M") -> dict:
    metrics = {}
    for name, avg in metrics_avg.items():
        metrics[f"{name}_avg"] = avg
        metrics[f"{name}_min"] = avg - 1
        metrics[f"{name}_max"] = avg + 1
        metrics[f"{name}_trend"] = 0.0
    return {
        "device_id": device_id,
        "station_id": device_id,
        "window_type": window_type,
        "window_start": t - 600,
        "window_end": t,
        "metrics": metrics,
        "anomalies": anomalies or [],
        "created_at": t,
    }


class _BrokenStore:
    """Simulates a Farm State Store that fails mid-call, to exercise the
    UPSTREAM_TIMEOUT path shared by all 4 tools."""

    def now(self):
        return time.time()

    def latest(self, *a, **kw):
        raise RuntimeError("boom")

    def series(self, *a, **kw):
        raise RuntimeError("boom")

    def all_device_ids(self):
        raise RuntimeError("boom")

    def has_seen_any_window_before(self, *a, **kw):
        raise RuntimeError("boom")


# --- get_device_snapshot ------------------------------------------------------


def test_snapshot_matches_docs_example_shape(store, ledger, settings):
    now = time.time()
    store.update_from_raw(_raw("SOIL_01", now - 12, soil_moisture=31.4, temperature=27.1))
    store.update_from_raw(_raw("TANK_01", now - 10, level=78.5))

    result = get_device_snapshot(store, ledger, settings, device_ids=["SOIL_01", "TANK_01"])

    assert result["ok"] is True
    assert result["data_completeness"] == "2/2"
    rows = {(r["device_id"], r["metric"]): r for r in result["rows"]}
    assert rows[("SOIL_01", "soil_moisture")]["value"] == "31.4"
    assert rows[("SOIL_01", "soil_moisture")]["unit"] == "%"
    assert rows[("SOIL_01", "soil_moisture")]["freshness"] == "FRESH"
    assert rows[("SOIL_01", "soil_moisture")]["evidence_id"].startswith("EV-")
    assert "data_completeness: 2/2" in result["markdown"]


def test_snapshot_empty_device_ids_means_all_six(store, ledger, settings):
    result = get_device_snapshot(store, ledger, settings, device_ids=[])
    devices = {r["device_id"] for r in result["rows"]}
    assert devices == {"SOIL_01", "WEATHER_01", "PUMP_01", "PH_01", "TANK_01", "SUN_01"}


def test_snapshot_never_seen_device_is_offline_no_evidence(store, ledger, settings):
    result = get_device_snapshot(store, ledger, settings, device_ids=["TANK_01"])
    row = result["rows"][0]
    assert row["value"] == "—"
    assert row["freshness"] == "OFFLINE"
    assert row["evidence_id"] == "—"
    assert result["data_completeness"] == "0/1"


def test_snapshot_unknown_device_id_is_error(store, ledger, settings):
    result = get_device_snapshot(store, ledger, settings, device_ids=["NOT_A_DEVICE"])
    assert result["ok"] is False
    assert result["error_code"] == "DEVICE_UNKNOWN"


def test_snapshot_upstream_timeout(ledger, settings):
    result = get_device_snapshot(_BrokenStore(), ledger, settings, device_ids=["SOIL_01"])
    assert result["ok"] is False
    assert result["error_code"] == "UPSTREAM_TIMEOUT"
    assert result["retryable"] is True


# --- get_metric_series ---------------------------------------------------------


def test_metric_series_happy_path(store, ledger, settings):
    now = time.time()
    store.update_from_raw(_raw("SOIL_01", now - 5, soil_moisture=31.0, temperature=27.0))
    for i in range(5):
        t = now - (5 - i) * 60
        store.update_from_window(_window("SOIL_01", t, {"soil_moisture": 30.0 + i}))

    result = get_metric_series(
        store,
        ledger,
        settings,
        device_id="SOIL_01",
        metric="soil_moisture",
        lookback_minutes=30,
        window_type="SLIDING_10M",  # matches the window_type the fixture windows were stored under
    )
    assert result["ok"] is True
    assert result["evidence_id"].startswith("EV-")
    assert result["last"] == 34.0  # last window's avg (30 + 4)


def test_metric_series_insufficient_data(store, ledger, settings):
    now = time.time()
    store.update_from_raw(_raw("SOIL_01", now - 5, soil_moisture=31.0, temperature=27.0))
    store.update_from_window(_window("SOIL_01", now - 60, {"soil_moisture": 30.0}))

    result = get_metric_series(
        store, ledger, settings, device_id="SOIL_01", metric="soil_moisture", lookback_minutes=30
    )
    assert result["ok"] is False
    assert result["error_code"] == "INSUFFICIENT_DATA"


def test_metric_series_device_offline(store, ledger, settings):
    result = get_metric_series(
        store, ledger, settings, device_id="SOIL_01", metric="soil_moisture", lookback_minutes=30
    )
    assert result["ok"] is False
    assert result["error_code"] == "DEVICE_OFFLINE"


def test_metric_series_invalid_lookback(store, ledger, settings):
    result = get_metric_series(
        store, ledger, settings, device_id="SOIL_01", metric="soil_moisture", lookback_minutes=9999
    )
    assert result["ok"] is False
    assert result["error_code"] == "INVALID_ARGUMENT"


def test_metric_series_metric_not_owned_by_device(store, ledger, settings):
    result = get_metric_series(
        store, ledger, settings, device_id="TANK_01", metric="soil_moisture", lookback_minutes=30
    )
    assert result["ok"] is False
    assert result["error_code"] == "INVALID_ARGUMENT"


def test_metric_series_upstream_timeout(ledger, settings):
    result = get_metric_series(
        _BrokenStore(), ledger, settings, device_id="SOIL_01", metric="soil_moisture", lookback_minutes=30
    )
    assert result["ok"] is False
    assert result["error_code"] == "UPSTREAM_TIMEOUT"


# --- get_freshness_report -------------------------------------------------------


def test_freshness_report_classifies_all_three_states(store, ledger, settings):
    now = time.time()
    store.update_from_raw(_raw("SOIL_01", now - 5, soil_moisture=31.0, temperature=27.0))  # FRESH
    store.update_from_raw(_raw("WEATHER_01", now - 200, temperature=26.0, humidity=70.0))  # STALE
    # PUMP_01, PH_01, TANK_01, SUN_01 never seen -> OFFLINE

    result = get_freshness_report(store, ledger, settings)

    assert result["ok"] is True
    assert result["fresh"] == ["SOIL_01"]
    assert result["stale"][0]["device_id"] == "WEATHER_01"
    offline_ids = {o["device_id"] for o in result["offline"]}
    assert offline_ids == {"PUMP_01", "PH_01", "TANK_01", "SUN_01"}
    assert result["data_completeness"] == "1/6"
    assert result["mode"] == "PARTIAL"

    absence_records = [r for r in ledger.all() if r.is_absence_record]
    assert len(absence_records) == 4


def test_freshness_report_upstream_timeout(ledger, settings):
    result = get_freshness_report(_BrokenStore(), ledger, settings)
    assert result["ok"] is False
    assert result["error_code"] == "UPSTREAM_TIMEOUT"


# --- get_anomaly_report ---------------------------------------------------------


def test_anomaly_report_cold_start_when_no_history(store, ledger, settings):
    result = get_anomaly_report(store, ledger, settings, zone="ZONE_A", lookback_minutes=60)
    assert result["ok"] is False
    assert result["error_code"] == "MODEL_COLD_START"
    assert result["retryable"] is True


def test_anomaly_report_returns_real_anomalies(store, ledger, settings):
    now = time.time()
    # Establish history reaching back further than the lookback window...
    store.update_from_window(_window("SOIL_01", now - 1200, {"soil_moisture": 30.0}))
    # ...then a recent window carrying a real rule-based anomaly.
    anomaly = {
        "type": "SOIL_MOISTURE_CRITICAL_LOW",
        "severity": "HIGH",
        "metric": "soil_moisture",
        "val": 9.5,
        "msg": "Độ ẩm đất quá thấp",
    }
    store.update_from_window(_window("SOIL_01", now - 60, {"soil_moisture": 9.5}, anomalies=[anomaly]))

    result = get_anomaly_report(store, ledger, settings, zone="ZONE_A", lookback_minutes=10)

    assert result["ok"] is True
    assert len(result["anomalies"]) == 1
    a = result["anomalies"][0]
    assert a["anomaly_type"] == "SOIL_MOISTURE_CRITICAL_LOW"
    assert a["device_id"] == "SOIL_01"
    assert a["score_0_1"] == 0.9
    assert a["model_version"] == "stream-rules-v1"
    assert a["evidence_refs"][0].startswith("EV-")


def test_anomaly_report_invalid_zone(store, ledger, settings):
    result = get_anomaly_report(store, ledger, settings, zone="ZONE_B", lookback_minutes=60)
    assert result["ok"] is False
    assert result["error_code"] == "INVALID_ARGUMENT"


def test_anomaly_report_upstream_timeout(ledger, settings):
    result = get_anomaly_report(_BrokenStore(), ledger, settings, zone="ZONE_A", lookback_minutes=60)
    assert result["ok"] is False
    assert result["error_code"] == "UPSTREAM_TIMEOUT"
