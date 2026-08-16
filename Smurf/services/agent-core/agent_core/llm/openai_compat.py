"""The single LLMClient implementation for agent-core.

LM Studio and Gemini both speak the OpenAI-compatible chat.completions
protocol (ADR-001), so one implementation parameterized by `base_url` /
`model` / `api_key` covers both providers. Nothing outside this file should
ever branch on which provider is active — see `agent_core.config.Settings.
llm_profile_config()` for the one place that resolves `LLM_PROFILE` into the
constructor arguments below.

M4.5 — Fault tolerance: a CircuitBreaker is wired into `chat()`. After
`CIRCUIT_FAILURE_THRESHOLD` consecutive transport failures the circuit opens
and subsequent calls return immediately with `error_code=CIRCUIT_OPEN`
instead of stalling for up to `timeout_sec` each time (which blocks
`GET /health` and the SSE stream). The circuit resets after
`CIRCUIT_RESET_SEC` when the provider comes back.
"""
from __future__ import annotations

import logging
import time

from openai import OpenAI

from .circuit_breaker import CIRCUIT_OPEN, CircuitBreaker
from .client import ChatCompletionResult

logger = logging.getLogger(__name__)

# Fault-tolerance knobs (M4.5). Keep defaults conservative — 3 failures in a
# row is a dead provider, not a transient hiccup; 30 s is enough to let LM
# Studio restart without spamming /health with CIRCUIT_OPEN.
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_RESET_SEC = 30.0


class OpenAICompatClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        model: str,
        api_key: str,
        timeout_sec: float = 60.0,
        circuit_failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
        circuit_reset_sec: float = CIRCUIT_RESET_SEC,
    ) -> None:
        self.provider = provider
        self.model = model
        self._timeout_sec = timeout_sec
        # LM Studio ignores the API key value but the SDK requires the field
        # to be non-empty (see services/agent-core/.env.example).
        # max_retries=0: retry policy is owned entirely by
        # structured_output.py (exactly 1 retry, bounded — rule 6). Letting
        # the SDK retry underneath it would double-spend that budget
        # invisibly and stall GET /health for ~9s when the LLM is down,
        # which the frontend is expected to poll every 5s (04-integration-
        # guide.md §3.2d).
        self._client = OpenAI(
            base_url=base_url, api_key=api_key or "not-needed", timeout=timeout_sec, max_retries=0
        )
        # M4.5: circuit breaker — prevents cascading stalls on dead provider
        self._circuit = CircuitBreaker(
            failure_threshold=circuit_failure_threshold,
            reset_sec=circuit_reset_sec,
            name=provider,
        )

    @property
    def circuit_state(self) -> str:
        """Current circuit breaker state: ``"CLOSED"``, ``"OPEN"``, or ``"HALF_OPEN"``.
        Exposed for ``GET /health`` so the frontend can distinguish "LLM slow"
        from "LLM dead and we gave up waiting".
        """
        return self._circuit.state

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        schema_name: str,
        temperature: float = 0.1,
        timeout_sec: float | None = None,
    ) -> ChatCompletionResult:
        # M4.5: short-circuit before touching the network if the circuit is open
        if not self._circuit.before_call():
            logger.warning(
                "LLM chat short-circuited (provider=%s circuit=OPEN)", self.provider
            )
            return ChatCompletionResult(
                ok=False,
                content="",
                model=self.model,
                provider=self.provider,
                duration_ms=0,
                error_message=CIRCUIT_OPEN,
            )

        started = time.monotonic()
        effective_timeout = timeout_sec if timeout_sec is not None else self._timeout_sec
        try:
            client = self._client.with_options(timeout=effective_timeout)
            response = client.chat.completions.create(
                model=self.model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": schema, "strict": True},
                },
            )
        except Exception as exc:  # noqa: BLE001 — normalize every provider error at this one boundary
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.warning(
                "LLM chat call failed (provider=%s model=%s schema=%s): %s",
                self.provider, self.model, schema_name, exc,
            )
            self._circuit.record_failure()  # M4.5: count toward threshold
            return ChatCompletionResult(
                ok=False,
                content="",
                model=self.model,
                provider=self.provider,
                duration_ms=duration_ms,
                error_message=str(exc),
            )

        self._circuit.record_success()  # M4.5: reset failure counter on success
        duration_ms = int((time.monotonic() - started) * 1000)
        choice = response.choices[0]
        usage = response.usage
        return ChatCompletionResult(
            ok=True,
            content=choice.message.content or "",
            model=self.model,
            provider=self.provider,
            duration_ms=duration_ms,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    def is_reachable(self) -> bool:
        try:
            self._client.with_options(timeout=5.0).models.list()
            return True
        except Exception:
            return False
