"""GET /api/v1/state/farm — docs/agent-core/03-contracts.md §4.5 annex.
"Hữu ích cho frontend ngay cả khi chưa có agent" — reads straight from the
Farm State Store, no LLM involved.
"""
from __future__ import annotations

from fastapi import APIRouter

from agent_core.devices import ZONE, Freshness, unit_for
from agent_core.state.freshness import clamp_age, data_completeness
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso


def build_state_router(store: FarmStateStore, settings) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/state/farm")
    def state_farm() -> dict:
        now = store.now()
        device_freshness: dict = {}
        devices_out = []
        for device_id in store.all_device_ids():
            summary = store.freshness_summary(
                device_id, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec
            )
            device_freshness[device_id] = summary.worst

            metrics_out = [
                {
                    "metric": metric.value,
                    "value_text": (
                        "—" if reading is None or freshness == Freshness.OFFLINE else f"{reading.value:g}"
                    ),
                    "unit": unit_for(device_id, metric),
                }
                for metric, reading, _age, freshness in summary.per_metric
            ]
            devices_out.append(
                {
                    "device_id": device_id.value,
                    "freshness": summary.worst.value,
                    "age_seconds": (
                        int(clamp_age(summary.worst_age)) if summary.worst_age is not None else None
                    ),
                    "last_seen_iso": to_iso(summary.worst_reading.observed_at) if summary.worst_reading else None,
                    "metrics": metrics_out,
                }
            )

        ratio, mode = data_completeness(device_freshness)
        return {
            "zone": ZONE,
            "snapshot_at_iso": to_iso(now),
            "data_completeness": ratio,
            "mode": mode,
            "devices": devices_out,
        }

    return router
