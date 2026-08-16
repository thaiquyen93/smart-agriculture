"""LLMClient protocol — the ONLY surface agent code (M2+) is allowed to see.

Per ADR-001 §"Hai kỷ luật bắt buộc để giữ tính khả chuyển", discipline #2:
provider-specific details (base_url, model name, native tool-calling on/off,
reasoning_effort, n_gpu_layers, ...) must never leak past
`agent_core.llm.openai_compat.OpenAICompatClient`. Everything above this
module only ever calls `.chat(...)` and `.is_reachable()`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ChatCompletionResult:
    """Raw result of one chat-completion call. `ok=False` covers transport/
    provider failures (timeout, connection refused, 4xx/5xx) — JSON parsing
    of `content` happens one layer up, in structured_output.py."""

    ok: bool
    content: str
    model: str
    provider: str
    duration_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error_message: str = ""


@runtime_checkable
class LLMClient(Protocol):
    provider: str
    model: str

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
        """One chat-completion call, constrained to `schema` via
        response_format. Must never raise — provider/transport failures come
        back as `ChatCompletionResult(ok=False, ...)`."""
        ...

    def is_reachable(self) -> bool:
        """Cheap liveness check for GET /health. Must never raise."""
        ...
