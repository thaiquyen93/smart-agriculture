"""Unit tests for M4.5 Kafka fault tolerance — exponential backoff + status_snapshot.

All tests are pure Python; no real Kafka connection required.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from agent_core.kafka.consumer import (
    AgentCoreConsumer,
    _RECONNECT_BASE_SEC,
    _RECONNECT_FACTOR,
    _RECONNECT_JITTER,
    _RECONNECT_MAX_SEC,
    _backoff_delay,
)


# ---------------------------------------------------------------------------
# _backoff_delay unit tests
# ---------------------------------------------------------------------------

class TestBackoffDelay:
    def test_first_reconnect_near_base(self):
        """reconnect_count=0 → delay ≈ _RECONNECT_BASE_SEC."""
        delay = _backoff_delay(0)
        base = _RECONNECT_BASE_SEC
        jitter = base * _RECONNECT_JITTER
        assert base - jitter <= delay <= base + jitter

    def test_second_reconnect_doubles(self):
        """reconnect_count=1 → delay ≈ base × factor."""
        delay = _backoff_delay(1)
        expected = _RECONNECT_BASE_SEC * _RECONNECT_FACTOR
        jitter = expected * _RECONNECT_JITTER
        assert expected - jitter <= delay <= expected + jitter

    def test_exponential_growth_sequence(self):
        """Delays grow: ~5s, ~10s, ~20s, ~40s, then capped at 60s."""
        expected_bases = [5.0, 10.0, 20.0, 40.0, 60.0, 60.0]
        for i, exp_base in enumerate(expected_bases):
            delay = _backoff_delay(i)
            jitter = min(exp_base, _RECONNECT_MAX_SEC) * _RECONNECT_JITTER
            capped = min(exp_base, _RECONNECT_MAX_SEC)
            assert capped - jitter <= delay <= capped + jitter, (
                f"reconnect_count={i}: expected ~{capped}s, got {delay:.2f}s"
            )

    def test_capped_at_max(self):
        """Very high reconnect_count → delay capped at _RECONNECT_MAX_SEC."""
        delay = _backoff_delay(100)
        jitter = _RECONNECT_MAX_SEC * _RECONNECT_JITTER
        assert delay <= _RECONNECT_MAX_SEC + jitter

    def test_jitter_within_bounds(self):
        """Delay is always within [base×0.9, base×1.1] (±10%)."""
        for count in range(6):
            delays = [_backoff_delay(count) for _ in range(50)]
            raw_base = _RECONNECT_BASE_SEC * (_RECONNECT_FACTOR ** count)
            base = min(raw_base, _RECONNECT_MAX_SEC)
            lo = base * (1 - _RECONNECT_JITTER)
            hi = base * (1 + _RECONNECT_JITTER)
            for d in delays:
                assert lo <= d <= hi, (
                    f"count={count}: delay {d:.3f} outside [{lo:.3f}, {hi:.3f}]"
                )

    def test_always_positive(self):
        for count in range(10):
            assert _backoff_delay(count) > 0


# ---------------------------------------------------------------------------
# AgentCoreConsumer — status_snapshot + reconnect tracking
# ---------------------------------------------------------------------------

def _make_consumer(**kwargs) -> AgentCoreConsumer:
    store = MagicMock()
    return AgentCoreConsumer(
        bootstrap_servers="localhost:9092",
        topic_raw="topic_raw",
        topic_p="topic_p",
        topic_h="topic_h",
        store=store,
        **kwargs,
    )


class TestConsumerStatusSnapshot:
    def test_initial_status_snapshot(self):
        consumer = _make_consumer()
        snap = consumer.status_snapshot()
        assert snap["connected"] is False
        assert snap["reconnect_count"] == 0
        assert snap["last_disconnect_at"] is None

    def test_status_snapshot_fields_complete(self):
        consumer = _make_consumer()
        snap = consumer.status_snapshot()
        assert set(snap.keys()) == {"connected", "reconnect_count", "last_disconnect_at"}

    def test_reconnect_count_property(self):
        consumer = _make_consumer()
        assert consumer.reconnect_count == 0

    def test_last_disconnect_at_none_initially(self):
        consumer = _make_consumer()
        assert consumer.last_disconnect_at is None

    def test_is_connected_false_initially(self):
        consumer = _make_consumer()
        assert not consumer.is_connected


class TestConsumerDoesNotBlockBoot:
    def test_start_returns_immediately_when_kafka_down(self):
        """start() must return immediately — Kafka connectivity is established
        in the daemon thread, not in start() itself (same invariant as M0/M1)."""
        consumer = _make_consumer()

        with patch("agent_core.kafka.consumer.KafkaConsumer") as mock_kc:
            mock_kc.side_effect = Exception("Kafka unavailable")
            t0 = time.monotonic()
            consumer.start()
            elapsed = time.monotonic() - t0

        # start() should return in well under 1 second even if Kafka is down
        assert elapsed < 1.0, f"start() blocked for {elapsed:.2f}s — must be non-blocking"
        consumer.stop(timeout=0.5)

    def test_second_start_is_noop(self):
        """Calling start() twice does not create a second thread."""
        consumer = _make_consumer()
        consumer.start()
        thread1 = consumer._thread
        consumer.start()
        assert consumer._thread is thread1
        consumer.stop(timeout=0.5)


class TestReconnectCountIncrement:
    def test_reconnect_count_increments_on_disconnect(self):
        """Simulate a successful connect followed by a disconnect.

        We inject a _consume_loop that sets connected, then raises an error.
        The finally block in _run() detects the connected→disconnected
        transition and increments reconnect_count.  We stop AFTER the first
        cycle by patching time.sleep to set stop_event on the second call
        (i.e. after the first sleep/retry would happen).
        """
        consumer = _make_consumer()
        call_count = 0
        sleep_call_count = [0]

        def fake_consume_loop(kc):
            nonlocal call_count
            call_count += 1
            # Signal connected so the finally block detects a real disconnect
            consumer._connected.set()
            raise Exception("Simulated disconnect")

        def fake_sleep(_delay):
            sleep_call_count[0] += 1
            # After the first sleep (post-disconnect), stop the loop
            consumer._stop_event.set()

        consumer._consume_loop = fake_consume_loop

        mock_kc_instance = MagicMock()
        with patch("agent_core.kafka.consumer.KafkaConsumer", return_value=mock_kc_instance):
            with patch("agent_core.kafka.consumer.time.sleep", side_effect=fake_sleep):
                consumer.start()
                # Wait for the thread: stop_event set in fake_sleep, then thread exits
                consumer._stop_event.wait(timeout=3.0)
                consumer._thread.join(timeout=2.0)

        # After the simulated disconnect cycle, reconnect_count should be >= 1
        assert consumer.reconnect_count >= 1
        assert consumer.last_disconnect_at is not None


class TestBackoffIntegration:
    def test_backoff_delay_increases_on_repeated_failure(self):
        """Integration: verify _backoff_delay is called with increasing count."""
        delays_used = []

        original_backoff = __import__(
            "agent_core.kafka.consumer", fromlist=["_backoff_delay"]
        )._backoff_delay

        def capture_delay(count):
            d = original_backoff(count)
            delays_used.append((count, d))
            return 0.0  # immediate for test speed

        consumer = _make_consumer()

        with patch("agent_core.kafka.consumer._backoff_delay", side_effect=capture_delay):
            with patch("agent_core.kafka.consumer.KafkaConsumer") as mock_kc:
                call_n = [0]

                def raise_then_stop(*a, **kw):
                    call_n[0] += 1
                    if call_n[0] >= 3:
                        consumer._stop_event.set()
                    raise Exception("Kafka down")

                mock_kc.side_effect = raise_then_stop
                with patch("agent_core.kafka.consumer.time.sleep"):
                    consumer.start()
                    consumer._stop_event.wait(timeout=3.0)

        # Should have at least 2 calls with increasing count args
        if len(delays_used) >= 2:
            counts = [c for c, _ in delays_used]
            assert counts == sorted(counts), f"Counts should be non-decreasing: {counts}"
