"""Unit tests for the retry/fallback policy in agent_core.llm.structured_output.

Uses a scripted stub LLMClient — no LM Studio required, so this stays green
on any machine (see tests/test_llm_client_live.py for the real-model
measurement).
"""
import pytest

from agent_core.llm.client import ChatCompletionResult
from agent_core.llm.structured_output import INVALID_JSON, UPSTREAM_TIMEOUT, complete_structured

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ok", "value"],
    "properties": {
        "ok": {"type": "boolean", "description": "Kết quả"},
        "value": {"type": "string", "description": "Giá trị"},
    },
}


class StubClient:
    """Feeds a scripted sequence of raw model responses, so retry/fallback
    logic can be tested deterministically."""

    provider = "stub"
    model = "stub-model"

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def chat(self, *, system_prompt, user_prompt, schema, schema_name, temperature=0.1, timeout_sec=None):
        self.calls += 1
        content = self._responses.pop(0)
        return ChatCompletionResult(
            ok=True, content=content, model=self.model, provider=self.provider,
            duration_ms=10, prompt_tokens=5, completion_tokens=5,
        )

    def is_reachable(self) -> bool:
        return True


class FailingClient:
    """Simulates a transport/provider failure (LM Studio down, timeout, ...)."""

    provider = "stub"
    model = "stub-model"

    def __init__(self):
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        return ChatCompletionResult(
            ok=False, content="", model=self.model, provider=self.provider,
            duration_ms=5, error_message="connection refused",
        )

    def is_reachable(self) -> bool:
        return False


def test_first_attempt_success_no_retry():
    client = StubClient(['{"ok": true, "value": "hi"}'])
    result = complete_structured(client, system_prompt="s", user_prompt="u", schema=SCHEMA, schema_name="test")

    assert result.ok is True
    assert result.data == {"ok": True, "value": "hi"}
    assert result.retry_count == 0
    assert client.calls == 1


def test_retries_once_then_succeeds():
    client = StubClient(["not json at all", '{"ok": true, "value": "recovered"}'])
    result = complete_structured(client, system_prompt="s", user_prompt="u", schema=SCHEMA, schema_name="test")

    assert result.ok is True
    assert result.data == {"ok": True, "value": "recovered"}
    assert result.retry_count == 1
    assert client.calls == 2


def test_falls_back_deterministically_after_exhausting_retry():
    client = StubClient(["garbage", "still garbage"])
    result = complete_structured(client, system_prompt="s", user_prompt="u", schema=SCHEMA, schema_name="test")

    assert result.ok is False
    assert result.data is None
    assert result.error_code == INVALID_JSON
    assert client.calls == 2


def test_non_object_json_counts_as_parse_failure():
    # A JSON array or scalar is valid JSON but not a JSON *object* — must
    # not be accepted as a structured-output result.
    client = StubClient(['["not", "an", "object"]', '{"ok": true, "value": "fixed"}'])
    result = complete_structured(client, system_prompt="s", user_prompt="u", schema=SCHEMA, schema_name="test")

    assert result.ok is True
    assert result.retry_count == 1


def test_transport_failure_does_not_retry():
    client = FailingClient()
    result = complete_structured(client, system_prompt="s", user_prompt="u", schema=SCHEMA, schema_name="test")

    assert result.ok is False
    assert result.error_code == UPSTREAM_TIMEOUT
    assert client.calls == 1  # no retry budget spent on a dead connection


def test_schema_violation_raises_before_calling_llm():
    bad_schema = {"type": "object", "properties": {"x": {"anyOf": [{"type": "string"}]}}}
    client = StubClient(["irrelevant"])

    with pytest.raises(ValueError):
        complete_structured(client, system_prompt="s", user_prompt="u", schema=bad_schema, schema_name="bad")

    assert client.calls == 0
