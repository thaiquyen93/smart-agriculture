"""Unit tests for M4.5 LLM fault tolerance — circuit_breaker + openai_compat.

All tests are pure Python; no network calls, no LLM, no Kafka required.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from agent_core.llm.circuit_breaker import CIRCUIT_OPEN, CircuitBreaker
from agent_core.llm.openai_compat import OpenAICompatClient


# ---------------------------------------------------------------------------
# CircuitBreaker unit tests
# ---------------------------------------------------------------------------

class TestCircuitBreakerStates:
    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, reset_sec=30.0)
        assert cb.state == "CLOSED"
        assert not cb.is_open
        assert cb.consecutive_failures == 0

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, reset_sec=30.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "CLOSED"  # still closed at 2
        cb.record_failure()
        assert cb.state == "OPEN"    # opens at 3
        assert cb.is_open

    def test_does_not_open_below_threshold(self):
        cb = CircuitBreaker(failure_threshold=5, reset_sec=30.0)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == "CLOSED"

    def test_before_call_returns_false_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, reset_sec=30.0)
        cb.record_failure()  # opens immediately
        assert cb.is_open
        assert cb.before_call() is False

    def test_before_call_returns_true_when_closed(self):
        cb = CircuitBreaker(failure_threshold=3, reset_sec=30.0)
        assert cb.before_call() is True

    def test_half_open_after_reset_sec(self):
        cb = CircuitBreaker(failure_threshold=1, reset_sec=0.05)
        cb.record_failure()
        assert cb.state == "OPEN"
        time.sleep(0.1)  # wait for reset_sec to elapse
        assert cb.state == "HALF_OPEN"

    def test_before_call_returns_true_in_half_open(self):
        cb = CircuitBreaker(failure_threshold=1, reset_sec=0.05)
        cb.record_failure()
        time.sleep(0.1)
        assert cb.state == "HALF_OPEN"
        assert cb.before_call() is True  # probe call allowed

    def test_closes_on_success_from_open(self):
        cb = CircuitBreaker(failure_threshold=1, reset_sec=0.05)
        cb.record_failure()
        time.sleep(0.1)            # → HALF_OPEN
        cb.record_success()        # → CLOSED
        assert cb.state == "CLOSED"
        assert cb.consecutive_failures == 0

    def test_reopens_if_probe_fails(self):
        cb = CircuitBreaker(failure_threshold=1, reset_sec=0.05)
        cb.record_failure()        # opens
        time.sleep(0.1)            # → HALF_OPEN
        cb.record_failure()        # probe failed → reopen
        assert cb.state == "OPEN"

    def test_success_resets_failure_counter(self):
        cb = CircuitBreaker(failure_threshold=5, reset_sec=30.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.consecutive_failures == 2
        cb.record_success()
        assert cb.consecutive_failures == 0
        assert cb.state == "CLOSED"

    def test_thread_safety_multiple_failures(self):
        """Multiple threads recording failures must not corrupt state."""
        import threading
        cb = CircuitBreaker(failure_threshold=10, reset_sec=60.0)
        threads = [threading.Thread(target=cb.record_failure) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All 10 failures recorded → circuit open
        assert cb.consecutive_failures == 10
        assert cb.state == "OPEN"


# ---------------------------------------------------------------------------
# OpenAICompatClient with circuit breaker
# ---------------------------------------------------------------------------

def _make_client(**kwargs) -> OpenAICompatClient:
    """Build a client with a mocked underlying OpenAI SDK."""
    return OpenAICompatClient(
        provider="local",
        base_url="http://localhost:1234/v1",
        model="qwen2.5-3b",
        api_key="test",
        **kwargs,
    )


class TestOpenAICompatCircuitBreaker:
    def test_short_circuits_when_circuit_open(self):
        """When the circuit is OPEN, chat() returns CIRCUIT_OPEN without network call."""
        client = _make_client(circuit_failure_threshold=1, circuit_reset_sec=60.0)

        # Force circuit open by simulating a transport failure
        with patch.object(client._client, "with_options") as mock_wo:
            mock_wo.return_value.chat.completions.create.side_effect = ConnectionError("refused")
            # First call: fails, opens circuit
            result = client.chat(
                system_prompt="sys", user_prompt="usr",
                schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                schema_name="TestSchema",
                timeout_sec=1.0,
            )
        assert not result.ok

        # Second call: circuit is open → short-circuit, zero network calls
        with patch.object(client._client, "with_options") as mock_wo2:
            result2 = client.chat(
                system_prompt="sys", user_prompt="usr",
                schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                schema_name="TestSchema",
            )
            mock_wo2.assert_not_called()  # no network attempt

        assert not result2.ok
        assert result2.error_message == CIRCUIT_OPEN
        assert result2.duration_ms == 0

    def test_records_failure_on_transport_error(self):
        client = _make_client(circuit_failure_threshold=5)
        with patch.object(client._client, "with_options") as mock_wo:
            mock_wo.return_value.chat.completions.create.side_effect = TimeoutError("timed out")
            client.chat(
                system_prompt="s", user_prompt="u",
                schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                schema_name="S",
                timeout_sec=0.001,
            )
        assert client._circuit.consecutive_failures == 1

    def test_records_success_on_valid_response(self):
        client = _make_client()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"ok": true}'
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        with patch.object(client._client, "with_options") as mock_wo:
            mock_wo.return_value.chat.completions.create.return_value = mock_response
            result = client.chat(
                system_prompt="s", user_prompt="u",
                schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                schema_name="S",
            )
        assert result.ok
        assert client._circuit.consecutive_failures == 0

    def test_circuit_state_property(self):
        client = _make_client(circuit_failure_threshold=3)
        assert client.circuit_state == "CLOSED"

    def test_does_not_retry_circuit_open_error_in_structured_output(self):
        """structured_output.complete_structured: transport failure (ok=False) is NOT retried.
        This means circuit_open (ok=False, error_code=CIRCUIT_OPEN) also won't be retried —
        the one retry budget is reserved for schema-parse failures only.
        """
        from agent_core.llm.structured_output import UPSTREAM_TIMEOUT, complete_structured

        client = _make_client(circuit_failure_threshold=1, circuit_reset_sec=60.0)

        # Open the circuit
        with patch.object(client._client, "with_options") as mock_wo:
            mock_wo.return_value.chat.completions.create.side_effect = ConnectionError("down")
            client.chat(
                system_prompt="s", user_prompt="u",
                schema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                schema_name="S",
                timeout_sec=0.001,
            )

        assert client._circuit.is_open

        schema = {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
            "additionalProperties": False,
        }
        result = complete_structured(
            client, system_prompt="s", user_prompt="u",
            schema=schema, schema_name="TestSchema",
        )
        # Must fail immediately — no retry attempted
        assert not result.ok
        assert result.retry_count == 0  # no retry for transport failure
        assert result.error_code == UPSTREAM_TIMEOUT
