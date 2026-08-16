"""AgentCoreConsumer — background daemon thread that feeds the Farm State
Store from topic_raw/topic_p/topic_h.

Must never block app boot or crash the process if Redpanda is unreachable
(same "never sacrifice availability for a dependency" rule M0 already
applied to the LLM client / GET /health) — connection happens in the
thread's own retry loop, not in __init__/start().

M4.5 — Fault tolerance: flat reconnect delay replaced with exponential
backoff (5s → 10s → 20s → 40s → 60s capped) with ±10% jitter so multiple
service instances don't all hammer Redpanda at the same time.  `reconnect_
count` and `last_disconnect_at` are exposed for `GET /health`.
"""
from __future__ import annotations

import logging
import random
import threading
import time

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from agent_core.state.store import FarmStateStore

logger = logging.getLogger(__name__)

# M4.5: exponential backoff knobs
_RECONNECT_BASE_SEC = 5.0
_RECONNECT_MAX_SEC = 60.0
_RECONNECT_FACTOR = 2.0
_RECONNECT_JITTER = 0.10  # ±10%
_POLL_TIMEOUT_MS = 1000


def _backoff_delay(reconnect_count: int) -> float:
    """Return the next reconnect delay with exponential backoff + jitter.

    Examples (before jitter): 5s, 10s, 20s, 40s, 60s (capped).
    """
    base = min(
        _RECONNECT_BASE_SEC * (_RECONNECT_FACTOR ** reconnect_count),
        _RECONNECT_MAX_SEC,
    )
    jitter = base * _RECONNECT_JITTER
    return base + random.uniform(-jitter, jitter)


class AgentCoreConsumer:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        topic_raw: str,
        topic_p: str,
        topic_h: str,
        store: FarmStateStore,
        group_id: str = "smurf-agent-core-group",
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic_raw = topic_raw
        self._topic_p = topic_p
        self._topic_h = topic_h
        self._group_id = group_id
        self._store = store

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = threading.Event()

        # M4.5: reconnect tracking (read by GET /health via status_snapshot())
        self._reconnect_count = 0
        self._last_disconnect_at: float | None = None
        self._tracking_lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    @property
    def reconnect_count(self) -> int:
        """Total number of times the consumer has (re)connected since start().
        Exposed for ``GET /health`` diagnostics.
        """
        with self._tracking_lock:
            return self._reconnect_count

    @property
    def last_disconnect_at(self) -> float | None:
        """Monotonic timestamp of the last disconnection, or ``None`` if the
        consumer has never disconnected.  Exposed for ``GET /health``.
        """
        with self._tracking_lock:
            return self._last_disconnect_at

    def status_snapshot(self) -> dict:
        """Return a JSON-serialisable dict summarising Kafka connectivity.

        Used by ``api/health.py`` to populate the ``kafka_detail`` field so
        operators can see how many reconnect cycles have occurred without
        digging through logs.
        """
        with self._tracking_lock:
            return {
                "connected": self._connected.is_set(),
                "reconnect_count": self._reconnect_count,
                "last_disconnect_at": self._last_disconnect_at,
            }

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="agent-core-kafka-consumer", daemon=True)
        self._thread.start()

    def stop(self, *, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            consumer = None
            try:
                consumer = KafkaConsumer(
                    self._topic_raw,
                    self._topic_p,
                    self._topic_h,
                    bootstrap_servers=self._bootstrap_servers.split(","),
                    group_id=self._group_id,
                    value_deserializer=_json_deserialize,
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                )
                logger.info(
                    "agent-core Kafka consumer connecting (bootstrap=%s, topics=[%s, %s, %s])",
                    self._bootstrap_servers, self._topic_raw, self._topic_p, self._topic_h,
                )
                self._consume_loop(consumer)
            except KafkaError as exc:
                delay = _backoff_delay(self._reconnect_count)  # M4.5
                logger.warning(
                    "Kafka consumer error, will retry in %.0fs (attempt %d): %s",
                    delay, self._reconnect_count + 1, exc,
                )
            except Exception:
                delay = _backoff_delay(self._reconnect_count)  # M4.5
                logger.exception(
                    "Unexpected error in agent-core Kafka consumer, will retry in %.0fs", delay
                )
            else:
                delay = _backoff_delay(self._reconnect_count)  # M4.5 (clean disconnect)
            finally:
                if self._connected.is_set():
                    # Record disconnect timestamp the first time we lose connection
                    with self._tracking_lock:
                        self._last_disconnect_at = time.monotonic()
                        self._reconnect_count += 1
                self._connected.clear()
                if consumer is not None:
                    try:
                        consumer.close()
                    except Exception:
                        pass
            if not self._stop_event.is_set():
                time.sleep(delay)  # M4.5: backoff delay (was flat _RECONNECT_DELAY_SEC)

    def _consume_loop(self, consumer: KafkaConsumer) -> None:
        # consumer.poll() (not the bare iterator) so the first call forces
        # group-join / partition assignment before we signal "connected" —
        # otherwise auto_offset_reset="latest" can resolve to "after this
        # poll", silently missing a message sent immediately after start().
        self._drain(consumer, timeout_ms=_POLL_TIMEOUT_MS)
        self._connected.set()
        logger.info("agent-core Kafka consumer connected and assigned partitions")
        while not self._stop_event.is_set():
            self._drain(consumer, timeout_ms=_POLL_TIMEOUT_MS)

    def _drain(self, consumer: KafkaConsumer, *, timeout_ms: int) -> None:
        records = consumer.poll(timeout_ms=timeout_ms)
        for batch in records.values():
            for message in batch:
                if self._stop_event.is_set():
                    return
                self._handle_message(message.topic, message.value)

    def _handle_message(self, topic: str, payload: dict | None) -> None:
        if payload is None:
            return
        try:
            if topic == self._topic_raw:
                self._store.update_from_raw(payload)
            elif topic in (self._topic_p, self._topic_h):
                self._store.update_from_window(payload)
        except Exception:
            logger.exception("Failed to process message from %s, skipping", topic)


def _json_deserialize(raw: bytes) -> dict | None:
    import json

    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        logger.warning("Dropping non-JSON Kafka message (%d bytes)", len(raw) if raw else 0)
        return None
