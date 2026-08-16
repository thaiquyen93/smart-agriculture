from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_core.state.store import FarmStateStore
from api.state import build_state_router


@pytest.fixture
def settings():
    return SimpleNamespace(freshness_fresh_sec=60, freshness_stale_sec=600)


@pytest.fixture
def client(tmp_path, settings):
    store = FarmStateStore(db_path=tmp_path / "farm_state.db")
    now = time.time()
    store.update_from_raw(
        {
            "device_id": "SOIL_01",
            "timestamp": now - 12,
            "event_time": now - 12,
            "soil_moisture": 31.4,
            "temperature": 27.1,
        }
    )
    app = FastAPI()
    app.include_router(build_state_router(store, settings))
    return TestClient(app)


def test_state_farm_matches_contract_shape(client):
    resp = client.get("/api/v1/state/farm")
    assert resp.status_code == 200
    body = resp.json()

    assert body["zone"] == "ZONE_A"
    assert "snapshot_at_iso" in body
    assert body["mode"] == "PARTIAL"  # only 1/6 devices FRESH
    assert body["data_completeness"] == "1/6"

    devices_by_id = {d["device_id"]: d for d in body["devices"]}
    assert len(devices_by_id) == 6

    soil = devices_by_id["SOIL_01"]
    assert soil["freshness"] == "FRESH"
    assert soil["age_seconds"] is not None
    metrics_by_name = {m["metric"]: m for m in soil["metrics"]}
    assert metrics_by_name["soil_moisture"]["value_text"] == "31.4"
    assert metrics_by_name["soil_moisture"]["unit"] == "%"

    tank = devices_by_id["TANK_01"]
    assert tank["freshness"] == "OFFLINE"
    assert tank["metrics"][0]["value_text"] == "—"
    assert tank["last_seen_iso"] is None
