"""FarmStateStore tests using payload shapes copied from the real producers
(services/ingestion-stream-engine/src/aggregators.py, farm_simulator.py) —
not guessed schemas. No Kafka/Redpanda needed."""
from __future__ import annotations

import time

import pytest

from agent_core.devices import DeviceId, Metric
from agent_core.state.store import FarmStateStore


def _raw_soil(t: float, moisture: float = 31.4, temp: float = 27.1) -> dict:
    return {
        "device_id": "SOIL_01",
        "timestamp": t,
        "event_time": t,
        "soil_moisture": moisture,
        "temperature": temp,
    }


def _raw_pump(t: float, flow: float = 12.5, power: float = 340.0, status: str = "ON") -> dict:
    return {
        "device_id": "PUMP_01",
        "timestamp": t,
        "event_time": t,
        "flow_rate": flow,
        "power": power,
        "status": status,  # non-numeric, must be ignored, not crash
    }


def _window_soil(t: float, *, window_type: str = "SLIDING_10M", anomalies: list | None = None) -> dict:
    return {
        "device_id": "SOIL_01",
        "station_id": "SOIL_01",
        "device_name": "SOIL_01",
        "region": "ZONE_A",
        "lat": 0.0,
        "lon": 0.0,
        "window_type": window_type,
        "window_start": t - 600,
        "window_end": t,
        "window_duration_sec": 600,
        "record_count": 10,
        "metrics": {
            "soil_moisture_avg": 31.0,
            "soil_moisture_min": 29.0,
            "soil_moisture_max": 33.0,
            "soil_moisture_trend": 0.5,
            "temperature_avg": 27.0,
            "temperature_min": 26.0,
            "temperature_max": 28.0,
            "temperature_trend": 0.1,
        },
        "anomalies": anomalies or [],
        "created_at": t,
    }


@pytest.fixture
def store(tmp_path):
    return FarmStateStore(db_path=tmp_path / "farm_state.db")


def test_update_from_raw_populates_latest(store):
    t = time.time()
    readings = store.update_from_raw(_raw_soil(t))
    assert {r.metric for r in readings} == {Metric.SOIL_MOISTURE, Metric.TEMPERATURE}

    reading = store.latest(DeviceId.SOIL_01, Metric.SOIL_MOISTURE)
    assert reading is not None
    assert reading.value == 31.4
    assert reading.unit == "%"
    assert reading.source_topic == "topic_raw"


def test_non_numeric_field_is_ignored_not_crashed(store):
    readings = store.update_from_raw(_raw_pump(time.time()))
    metrics = {r.metric for r in readings}
    assert metrics == {Metric.FLOW_RATE, Metric.POWER}  # "status" silently skipped


def test_unknown_device_id_is_skipped(store):
    payload = {"device_id": "STN_HN_01", "event_time": time.time(), "temp": 30.0}
    readings = store.update_from_raw(payload)
    assert readings == []


def test_out_of_order_raw_message_does_not_overwrite_newer_value(store):
    t = time.time()
    store.update_from_raw(_raw_soil(t, moisture=40.0))
    store.update_from_raw(_raw_soil(t - 100, moisture=99.0))  # older, must be ignored
    reading = store.latest(DeviceId.SOIL_01, Metric.SOIL_MOISTURE)
    assert reading.value == 40.0


def test_latest_for_device_reports_none_for_unseen_metric(store):
    result = store.latest_for_device(DeviceId.TANK_01)
    assert result == {Metric.LEVEL: None}


def test_update_from_window_populates_series(store):
    t = time.time()
    store.update_from_window(_window_soil(t))
    points = store.series(DeviceId.SOIL_01, Metric.SOIL_MOISTURE, window_type="SLIDING_10M")
    assert len(points) == 1
    assert points[0].avg == 31.0
    assert points[0].trend == 0.5


def test_update_from_window_does_not_touch_latest_reading(store):
    """Design decision: topic_raw drives 'current value', topic_p/h do not."""
    t = time.time()
    store.update_from_window(_window_soil(t))
    assert store.latest(DeviceId.SOIL_01, Metric.SOIL_MOISTURE) is None


def test_update_from_window_captures_anomalies(store):
    t = time.time()
    anomalies = [
        {
            "type": "SOIL_MOISTURE_CRITICAL_LOW",
            "severity": "HIGH",
            "metric": "soil_moisture",
            "val": 9.5,
            "msg": "Độ ẩm đất quá thấp",
        }
    ]
    store.update_from_window(_window_soil(t, anomalies=anomalies))
    events = store.anomalies_since(since=t - 10)
    assert len(events) == 1
    assert events[0].anomaly_type == "SOIL_MOISTURE_CRITICAL_LOW"
    assert events[0].device_id == DeviceId.SOIL_01
    assert events[0].severity == "HIGH"


def test_has_seen_any_window_before_tracks_cold_start(store):
    t = time.time()
    assert store.has_seen_any_window_before(t) is False
    store.update_from_window(_window_soil(t))
    assert store.has_seen_any_window_before(t + 1) is True


def test_state_survives_restart_via_sqlite(tmp_path):
    db_path = tmp_path / "farm_state.db"
    t = time.time()

    store1 = FarmStateStore(db_path=db_path)
    store1.update_from_raw(_raw_soil(t))

    store2 = FarmStateStore(db_path=db_path)  # simulate restart: fresh in-memory dict, same DB file
    reading = store2.latest(DeviceId.SOIL_01, Metric.SOIL_MOISTURE)
    assert reading is not None
    assert reading.value == 31.4
