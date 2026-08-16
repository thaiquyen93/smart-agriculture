"""Live integration test against a real Redpanda instance
(`docker compose up -d redpanda`, KAFKA_BOOTSTRAP_SERVERS default
localhost:9092). Publishes one real topic_raw message and measures how
long AgentCoreConsumer takes to land it in the Farm State Store — same
"measure, don't guess" approach as M0's test_llm_client_live.py.

Self-skips (not fails) when Redpanda is unreachable, so the rest of the
suite stays green without it running.

Note: `docker-compose.yml`'s `stream-engine` bridges MQTT topic
`hackathon/smurf/test/telemetry` on the **public** broker.hivemq.com into
topic_raw — that topic is shared across every team running this hackathon's
`farm_simulator.py`, so genuine SOIL_01 readings can arrive on topic_raw
from someone else's simulator at any moment, racing this test's own
message. The physically-impossible sentinel value below (soil_moisture
can't really be >100%) is what makes the assertion collision-proof, not
just the observed_at ordering.

Run with `-s` to see the measured latency:
    pytest services/agent-core/tests/test_kafka_consumer_live.py -v -s
"""
from __future__ import annotations

import json
import time

import pytest
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from agent_core.config import Settings
from agent_core.kafka.consumer import AgentCoreConsumer
from agent_core.devices import DeviceId, Metric
from agent_core.state.store import FarmStateStore

_CONNECT_TIMEOUT_SEC = 5.0
_POLL_TIMEOUT_SEC = 15.0


@pytest.fixture(scope="module")
def settings():
    return Settings.from_env()


@pytest.fixture(scope="module")
def producer(settings):
    try:
        p = KafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=str.encode,
            request_timeout_ms=int(_CONNECT_TIMEOUT_SEC * 1000),
            api_version_auto_timeout_ms=int(_CONNECT_TIMEOUT_SEC * 1000),
        )
    except NoBrokersAvailable:
        pytest.skip("Redpanda không reachable ở KAFKA_BOOTSTRAP_SERVERS — bỏ qua test live")
    yield p
    p.close()


def test_raw_message_lands_in_farm_state_store(tmp_path, settings, producer):
    store = FarmStateStore(db_path=tmp_path / "farm_state.db")
    consumer = AgentCoreConsumer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic_raw=settings.topic_raw,
        topic_p=settings.topic_p,
        topic_h=settings.topic_h,
        store=store,
        group_id=f"smurf-agent-core-test-{int(time.time())}",  # fresh group -> always gets the new message
    )
    consumer.start()

    started = time.monotonic()
    while not consumer.is_connected and time.monotonic() - started < _CONNECT_TIMEOUT_SEC * 2:
        time.sleep(0.2)
    if not consumer.is_connected:
        consumer.stop()
        pytest.skip("AgentCoreConsumer không connect được tới Redpanda trong thời gian chờ")

    test_value = 8675.309  # physically impossible for soil_moisture% — can't collide with real traffic
    sent_at = time.time()
    producer.send(
        settings.topic_raw,
        key="SOIL_01",
        value={
            "device_id": "SOIL_01",
            "timestamp": sent_at,
            "event_time": sent_at,
            "soil_moisture": test_value,
            "temperature": 22.2,
        },
    )
    producer.flush()

    # Match on the sentinel VALUE, not just "some recent update": real
    # concurrent traffic on the shared broker can otherwise overwrite our
    # reading in the store (out-of-order-protected, newest-wins) between
    # our send and the next poll tick.
    poll_started = time.monotonic()
    reading = None
    while time.monotonic() - poll_started < _POLL_TIMEOUT_SEC:
        reading = store.latest(DeviceId.SOIL_01, Metric.SOIL_MOISTURE)
        if reading is not None and reading.value == test_value:
            break
        time.sleep(0.2)

    consumer.stop()

    elapsed = time.monotonic() - poll_started
    print(f"\n[M1.1] topic_raw -> Farm State Store latency: {elapsed:.2f}s")

    assert reading is not None, "message không tới Farm State Store trong thời gian chờ"
    assert reading.value == test_value
