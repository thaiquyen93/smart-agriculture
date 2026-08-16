"""Structured-output layer — forces an LLM response into validated JSON,
with one retry on parse failure and a deterministic fallback.

This is roadmap milestone M0.3 — the single highest-risk item in the whole
project (docs/agent-core/07-roadmap.md): if qwen2.5-3b-instruct can't
reliably hold a JSON schema, every agent built on top of this module is
compromised. See tests/test_llm_client_live.py for the actual measurement
against the running LM Studio instance — this module implements the policy,
it doesn't guess whether the model is good enough.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from ..schema_lint import assert_schema_ok
from .client import ChatCompletionResult, LLMClient

logger = logging.getLogger(__name__)

# Unified error shape (docs/agent-core/02-agents-and-tools.md §A.3) — every
# tool/LLM-call failure in agent-core looks like this, so prompts never have
# to teach the model a dozen different failure shapes.
UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"  # the chat call itself failed (transport/provider)
INVALID_JSON = "INVALID_JSON"  # model output never parsed as a JSON object, even after retry


@dataclass
class StructuredCompletion:
    ok: bool
    data: dict | None
    retry_count: int
    raw_attempts: list[str] = field(default_factory=list)
    error_code: str = ""
    message: str = ""
    duration_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    provider: str = ""


def _try_parse_object(content: str) -> dict | None:
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def complete_structured(
    client: LLMClient,
    *,
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    schema_name: str,
    temperature: float = 0.1,
    timeout_sec: float = 60.0,
) -> StructuredCompletion:
    """Call `client`, forcing the response into `schema`.

    Stopping condition (rule 6, bounded orchestration — never a free loop):
    1. Lint `schema` first (raises ValueError before any network call if it
       violates the LM Studio/Gemini intersection rule — a bug to catch at
       schema-authoring time, not at demo time).
    2. One call. Valid JSON object -> return it immediately.
    3. Not valid JSON -> exactly ONE retry, with the parse failure fed back
       into the prompt.
    4. Still not valid -> deterministic fallback (`ok=False`, unified error
       shape). Never raises into agent code, never loops further.

    A transport/provider failure (`ChatCompletionResult.ok=False`) is NOT
    retried — retrying a dead connection wastes the one retry budget that
    schema-repair actually needs.
    """
    assert_schema_ok(schema, schema_name=schema_name)

    attempts: list[str] = []
    total_duration_ms = 0
    last_result: ChatCompletionResult | None = None

    for attempt in range(2):  # 1 initial call + 1 retry — explicit stopping condition (§A.1.5)
        prompt = user_prompt
        if attempt == 1 and last_result is not None:
            prompt = (
                f"{user_prompt}\n\n"
                f"Lượt trước bạn trả lời KHÔNG đúng định dạng JSON yêu cầu:\n"
                f"{last_result.content!r}\n"
                f"Hãy trả lại DUY NHẤT một JSON object hợp lệ khớp đúng schema, không kèm giải thích "
                f"hay markdown code fence."
            )

        result = client.chat(
            system_prompt=system_prompt,
            user_prompt=prompt,
            schema=schema,
            schema_name=schema_name,
            temperature=temperature,
            timeout_sec=timeout_sec,
        )
        last_result = result
        total_duration_ms += result.duration_ms
        attempts.append(result.content)

        if not result.ok:
            return StructuredCompletion(
                ok=False,
                data=None,
                retry_count=attempt,
                raw_attempts=attempts,
                error_code=UPSTREAM_TIMEOUT,
                message=result.error_message,
                duration_ms=total_duration_ms,
                model=result.model,
                provider=result.provider,
            )

        parsed = _try_parse_object(result.content)
        if parsed is not None:
            return StructuredCompletion(
                ok=True,
                data=parsed,
                retry_count=attempt,
                raw_attempts=attempts,
                duration_ms=total_duration_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                model=result.model,
                provider=result.provider,
            )

        logger.warning(
            "Structured output parse failed (attempt %d/2, schema=%s): %r",
            attempt + 1, schema_name, result.content,
        )

    return StructuredCompletion(
        ok=False,
        data=None,
        retry_count=1,
        raw_attempts=attempts,
        error_code=INVALID_JSON,
        message=f"Model không trả JSON hợp lệ sau {len(attempts)} lượt cho schema '{schema_name}'.",
        duration_ms=total_duration_ms,
        model=last_result.model if last_result else "",
        provider=last_result.provider if last_result else "",
    )
