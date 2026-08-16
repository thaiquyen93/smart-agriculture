"""agent-core FastAPI entrypoint.

M0: FastAPI skeleton, LLM client, GET /health.
M1: Farm State Store + Kafka consumer (topic_raw/p/h) + Evidence Ledger + GET /api/v1/state/farm.
M2 (this revision): Multi-Agent orchestration (Router/Coordinator/Workers/Action/Verifier/Narrative),
Kafka producers (5 output topics), REST API (sessions, plans, tasks, SSE streaming).

The Kafka consumer connects in its own background thread (agent_core.kafka.
consumer.AgentCoreConsumer) and retries forever — app startup never blocks
on or fails because of Redpanda being down, same availability promise M0
already made for the LLM client.
"""
from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI

from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.kafka.consumer import AgentCoreConsumer
from agent_core.kafka.producer import AgentEventProducer
from agent_core.llm.openai_compat import OpenAICompatClient
from agent_core.orchestrator import Orchestrator
from agent_core.state.store import FarmStateStore
from api import plans, sessions, tasks
from api.health import build_health_router
from api.state import build_state_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("agent_core.main")


def create_app() -> FastAPI:
    settings = Settings.from_env()
    profile = settings.llm_profile_config()

    llm_client = OpenAICompatClient(
        provider=profile.profile,
        base_url=profile.base_url,
        model=profile.model,
        api_key=profile.api_key,
        timeout_sec=profile.timeout_sec,
    )

    store = FarmStateStore(db_path="data/farm_state.db")
    ledger = EvidenceLedger()
    consumer = AgentCoreConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic_raw=settings.topic_raw,
        topic_p=settings.topic_p,
        topic_h=settings.topic_h,
        store=store,
    )

    # M2: Kafka producer for output events
    producer = AgentEventProducer(settings)
    producer.connect()

    # M2: Orchestrator
    orchestrator = Orchestrator(store, ledger, settings, producer, llm_client)

    app = FastAPI(title="SMURF agent-core", version="0.3.0")
    app.state.settings = settings
    app.state.store = store
    app.state.ledger = ledger
    app.state.consumer = consumer
    app.state.producer = producer
    app.state.orchestrator = orchestrator

    # M0/M1 routes
    app.include_router(build_health_router(settings, llm_client, store, consumer))
    app.include_router(build_state_router(store, settings))

    # M2 routes
    sessions.set_orchestrator(orchestrator)
    app.include_router(sessions.router)
    app.include_router(plans.router)
    app.include_router(tasks.router)

    @app.on_event("startup")
    def _start_consumer() -> None:
        consumer.start()

    @app.on_event("shutdown")
    def _stop_consumer() -> None:
        consumer.stop()
        producer.close()

    return app


app = create_app()

if __name__ == "__main__":
    settings: Settings = app.state.settings
    logger.info(
        "Starting agent-core on port %d (LLM_PROFILE=%s, KAFKA_BOOTSTRAP_SERVERS=%s)",
        settings.agent_core_port,
        settings.llm_profile,
        settings.kafka_bootstrap_servers,
    )
    uvicorn.run(app, host="0.0.0.0", port=settings.agent_core_port)
