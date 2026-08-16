"""Tests for the baseline `AnomalyDetector` (roadmap M3, docs/agent-core/
05-ml-interfaces.md §3.4) — Isolation Forest (Part A) + 3 cross-device
consistency rules (Part B). Called directly against the module, no LLM/tool
wiring involved (that's out of scope for the ML layer)."""
from __future__ import annotations

import pandas as pd
import pytest

from agent_core.models.baseline.anomaly import AnomalyDetectorBaseline

RULE_BASED_ANOMALY_TYPES = {
    "SUSPECTED_PIPE_BREAK_OR_SENSOR_FAULT",
    "SUSPECTED_TANK_LEAK",
    "SUSPECTED_WEATHER_SENSOR_FAULT",
}

FULL_COLUMNS = [
    "soil_moisture_avg", "soil_moisture_trend",
    "soil_temperature_avg", "soil_temperature_trend",
    "weather_temperature_avg", "weather_temperature_trend",
    "humidity_avg", "humidity_trend",
    "flow_rate_avg", "flow_rate_trend",
    "power_avg", "power_trend",
    "ph_avg", "ph_trend",
    "level_avg", "level_trend",
    "lux_avg", "lux_trend",
]


@pytest.fixture
def detector():
    return AnomalyDetectorBaseline()


def _normal_windows(n: int = 50, start_ts: float = 1_700_000_000.0) -> pd.DataFrame:
    """~n rows, 1 minute apart, every value oscillating gently around a
    stable mean with physically-sane cross-device relationships:
    pump running continuously -> soil moisture rises steadily; tank level
    drains slowly while the pump runs (never while flow ~ 0); lux/temperature
    move together in an ordinary daytime pattern (no sudden drop)."""
    rows = []
    for i in range(n):
        ts = start_ts + i * 60
        wobble = 0.05 * ((i % 5) - 2)  # small deterministic +-0.1 noise, no RNG needed
        rows.append(
            {
                "ts": ts,
                "soil_moisture_avg": 40.0 + 0.1 * i + wobble,
                "soil_moisture_trend": 0.1 + wobble * 0.1,
                "soil_temperature_avg": 22.0 + wobble,
                "soil_temperature_trend": wobble * 0.05,
                "weather_temperature_avg": 25.0 + 0.3 * wobble,
                "weather_temperature_trend": wobble * 0.05,
                "humidity_avg": 60.0 + wobble,
                "humidity_trend": wobble * 0.05,
                "flow_rate_avg": 5.0 + wobble * 0.2,
                "flow_rate_trend": wobble * 0.05,
                "power_avg": 600.0 + wobble * 2,
                "power_trend": wobble * 0.1,
                "ph_avg": 6.5 + wobble * 0.05,
                "ph_trend": wobble * 0.01,
                "level_avg": 80.0 - 0.05 * i + wobble * 0.1,
                "level_trend": -0.05 + wobble * 0.01,
                "lux_avg": 500.0 + wobble * 10,
                "lux_trend": wobble,
            }
        )
    return pd.DataFrame(rows)


# --- Part A: Isolation Forest ------------------------------------------------


def test_normal_windows_have_no_rule_based_anomalies(detector):
    windows = _normal_windows()
    anomalies = detector.detect("ZONE_A", windows)

    types = {a.anomaly_type for a in anomalies}
    assert not (types & RULE_BASED_ANOMALY_TYPES)


def test_power_spike_row_is_flagged_by_isolation_forest(detector):
    windows = _normal_windows()
    # One row with a huge, otherwise-unexplained power spike -> multivariate outlier.
    spike_idx = len(windows) // 2
    windows.loc[spike_idx, "power_avg"] = 6000.0

    anomalies = detector.detect("ZONE_A", windows)
    iso_anomalies = [a for a in anomalies if a.model_version == "isoforest-0.1"]

    assert len(iso_anomalies) >= 1
    assert any(a.contributing_features for a in iso_anomalies)
    assert all(a.anomaly_type == "MULTIVARIATE_OUTLIER" for a in iso_anomalies)
    assert all(0.0 <= a.score_0_1 <= 1.0 for a in iso_anomalies)


# --- Part B rule 1: pipe break / dead soil sensor ----------------------------


def test_sustained_flow_without_soil_moisture_rise_flags_pipe_break(detector):
    n = 15  # 15 rows, 1 min apart -> 14 min sustained flow, >= MIN_SUSTAINED_MINUTES
    rows = []
    for i in range(n):
        rows.append(
            {
                "ts": 1_700_000_000.0 + i * 60,
                "soil_moisture_avg": 30.0,  # flat - pump running but soil not getting wetter
                "soil_moisture_trend": 0.0,
                "flow_rate_avg": 5.0,  # sustained > FLOW_ZERO_EPS throughout
                "flow_rate_trend": 0.0,
                "level_avg": 80.0,  # constant - don't also trip the tank-leak rule
                "weather_temperature_avg": 25.0,  # constant - don't trip weather rule
                "lux_avg": 500.0,
            }
        )
    windows = pd.DataFrame(rows)

    anomalies = detector.detect("ZONE_A", windows)
    matches = [a for a in anomalies if a.anomaly_type == "SUSPECTED_PIPE_BREAK_OR_SENSOR_FAULT"]

    assert len(matches) == 1
    assert matches[0].device_id == "SOIL_01"
    assert matches[0].model_version == "cross-device-rules-v1"
    assert set(matches[0].contributing_features) == {"flow_rate_avg", "soil_moisture_avg"}


def test_short_flow_burst_does_not_flag_pipe_break(detector):
    """A flow burst shorter than MIN_SUSTAINED_MINUTES must not trigger the
    rule, even if soil moisture stays flat - it's not "sustained"."""
    rows = []
    for i in range(3):  # only 2 minutes of sustained flow
        rows.append(
            {
                "ts": 1_700_000_000.0 + i * 60,
                "soil_moisture_avg": 30.0,
                "flow_rate_avg": 5.0,
                "level_avg": 80.0,
                "weather_temperature_avg": 25.0,
                "lux_avg": 500.0,
            }
        )
    windows = pd.DataFrame(rows)

    anomalies = detector.detect("ZONE_A", windows)
    assert not any(a.anomaly_type == "SUSPECTED_PIPE_BREAK_OR_SENSOR_FAULT" for a in anomalies)


# --- Part B rule 2: tank leak -------------------------------------------------


def test_level_drop_with_no_flow_flags_tank_leak(detector):
    n = 8
    rows = []
    for i in range(n):
        rows.append(
            {
                "ts": 1_700_000_000.0 + i * 60,
                "level_avg": 80.0 - 1.0 * i,  # steady 1%/min drop, well above TANK_LEVEL_DROP_EPS
                "flow_rate_avg": 0.0,  # pump not running throughout - not a normal drawdown
                "soil_moisture_avg": 30.0,  # flow is ~0, rule 1 stays silent regardless
            }
        )
    windows = pd.DataFrame(rows)

    anomalies = detector.detect("ZONE_A", windows)
    matches = [a for a in anomalies if a.anomaly_type == "SUSPECTED_TANK_LEAK"]

    assert len(matches) >= 1
    assert matches[0].device_id == "TANK_01"
    assert matches[0].model_version == "cross-device-rules-v1"
    assert set(matches[0].contributing_features) == {"level_avg", "flow_rate_avg"}


def test_level_drop_with_active_flow_is_normal_drawdown(detector):
    """A level drop while the pump is actively running is expected
    irrigation usage, not a leak."""
    n = 8
    rows = []
    for i in range(n):
        rows.append(
            {
                "ts": 1_700_000_000.0 + i * 60,
                "level_avg": 80.0 - 1.0 * i,
                "flow_rate_avg": 5.0,  # pump running - explains the drawdown
                "soil_moisture_avg": 30.0 + 0.1 * i,
            }
        )
    windows = pd.DataFrame(rows)

    anomalies = detector.detect("ZONE_A", windows)
    assert not any(a.anomaly_type == "SUSPECTED_TANK_LEAK" for a in anomalies)


# --- Part B rule 3: weather sensor fault -------------------------------------


def test_high_lux_with_sudden_temp_drop_flags_weather_sensor_fault(detector):
    lux_values = [100.0] * 7 + [900.0, 900.0, 900.0]  # top 30% of rows are "high lux"
    temp_values = [25.0] * 7 + [25.0, 18.0, 18.0]  # sharp drop right where lux goes high
    rows = []
    for i, (lux, temp) in enumerate(zip(lux_values, temp_values)):
        rows.append(
            {
                "ts": 1_700_000_000.0 + i * 60,
                "lux_avg": lux,
                "weather_temperature_avg": temp,
            }
        )
    windows = pd.DataFrame(rows)

    anomalies = detector.detect("ZONE_A", windows)
    matches = [a for a in anomalies if a.anomaly_type == "SUSPECTED_WEATHER_SENSOR_FAULT"]

    assert len(matches) >= 1
    assert matches[0].device_id == "WEATHER_01"
    assert matches[0].model_version == "cross-device-rules-v1"
    assert set(matches[0].contributing_features) == {"lux_avg", "weather_temperature_avg"}


def test_high_lux_with_stable_temp_is_not_flagged(detector):
    lux_values = [100.0] * 7 + [900.0, 900.0, 900.0]
    temp_values = [25.0] * 10  # no drop at all
    rows = []
    for i, (lux, temp) in enumerate(zip(lux_values, temp_values)):
        rows.append(
            {
                "ts": 1_700_000_000.0 + i * 60,
                "lux_avg": lux,
                "weather_temperature_avg": temp,
            }
        )
    windows = pd.DataFrame(rows)

    anomalies = detector.detect("ZONE_A", windows)
    assert not any(a.anomaly_type == "SUSPECTED_WEATHER_SENSOR_FAULT" for a in anomalies)


# --- Edge cases ---------------------------------------------------------------


def test_empty_windows_returns_empty_list(detector):
    windows = pd.DataFrame(columns=["ts", *FULL_COLUMNS])
    assert detector.detect("ZONE_A", windows) == []


def test_missing_most_columns_does_not_raise(detector):
    rows = [
        {"ts": 1_700_000_000.0 + i * 60, "soil_moisture_avg": 30.0, "flow_rate_avg": 0.0}
        for i in range(5)
    ]
    windows = pd.DataFrame(rows)

    result = detector.detect("ZONE_A", windows)

    assert isinstance(result, list)


def test_missing_ts_column_does_not_raise(detector):
    windows = pd.DataFrame([{"soil_moisture_avg": 30.0, "flow_rate_avg": 0.0}])
    assert detector.detect("ZONE_A", windows) == []
