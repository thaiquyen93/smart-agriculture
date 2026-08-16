"""GET /health — docs/agent-core/03-contracts.md §4.5.

Cam kết ở docs/agent-core/04-integration-guide.md §9: "GET /health luôn trả
về được, kể cả khi LLM chết (llm_reachable: false)" — extended in M1 to the
same promise for Kafka: `kafka_connected: false` is a valid, honest answer,
never a crash.
"""
from __future__ import annotations

from fastapi import APIRouter

from agent_core.config import Settings
from agent_core.devices import Freshness
from agent_core.kafka.consumer import AgentCoreConsumer
from agent_core.llm.client import LLMClient
from agent_core.state.store import FarmStateStore


def build_health_router(
    settings: Settings,
    llm_client: LLMClient,
    store: FarmStateStore | None = None,
    consumer: AgentCoreConsumer | None = None,
) -> APIRouter:
    """Factory so main.py controls dependency wiring explicitly instead of
    hiding Settings/LLMClient/Store/Consumer behind module-level globals.
    `store`/`consumer` are optional so M0-era callers/tests keep working
    without a Farm State Store."""
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        try:
            llm_reachable = llm_client.is_reachable()
        except Exception:
            llm_reachable = False

        return {
            "status": "ok",
            "llm_provider": settings.llm_profile,
            "llm_reachable": llm_reachable,
            "kafka_connected": consumer.is_connected if consumer is not None else False,
            "devices_fresh": _devices_fresh(store, settings) if store is not None else "0/6",
        }

    return router


def _devices_fresh(store: FarmStateStore, settings: Settings) -> str:
    try:
        fresh_count = sum(
            1
            for device_id in store.all_device_ids()
            if store.freshness_summary(
                device_id, fresh_sec=settings.freshness_fresh_sec, stale_sec=settings.freshness_stale_sec
            ).worst
            == Freshness.FRESH
        )
        return f"{fresh_count}/{len(store.all_device_ids())}"
    except Exception:
        return "0/6"
