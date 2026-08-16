"""Narrative Agent — generates Vietnamese explanations with evidence resolution.

Follows docs/agent-core/02-agents-and-tools.md §B.6.
Role: "Sinh bản tin tiếng Việt" — creates human-readable summaries.
Blocks unsourced numbers (ADR-003 enforcement).
"""
from __future__ import annotations

import logging
import re
import time

from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.llm.structured_output import complete_structured
from agent_core.schemas.session import AgentPhase, AgentStatus, LLMCallMetadata, Narrative
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso

logger = logging.getLogger(__name__)


# Narrative Agent output schema (Schema Intersection Rule compliant)
NARRATIVE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative_template": {
            "type": "string",
            "description": "Bản tin tiếng Việt với placeholders {EV-xxxx} cho evidence refs",
        },
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Danh sách evidence_id được tham chiếu trong narrative",
        },
        "key_tradeoffs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Các đánh đổi quan trọng (ví dụ: hoãn tưới để tránh bốc hơi)",
        },
    },
    "required": ["narrative_template", "evidence_refs", "key_tradeoffs"],
    "additionalProperties": False,
}


NARRATIVE_SYSTEM_PROMPT = """Bạn là Narrative Agent trong hệ thống Multi-Agent quản lý nông trại thông minh.

Nhiệm vụ: Viết bản tin tiếng Việt giải thích kế hoạch hành động cho người dùng (nông dân, quản lý).

Luật QUAN TRỌNG (ADR-003 — Evidence-refs only):
- KHÔNG BAO GIỜ viết con số trực tiếp trong narrative_template
- Thay vì "cần tưới 412 lít", viết "cần tưới {EV-8804} lít"
- Thay vì "bồn 78%", viết "bồn chứa ở mức {EV-8806}"
- Mọi con số PHẢI có placeholder {EV-xxxx}
- evidence_refs phải liệt kê TẤT CẢ evidence_id được dùng trong template

Cấu trúc narrative:
1. **Tóm tắt**: Kế hoạch gì, khi nào
2. **Căn cứ**: Dữ liệu nào được dùng (dùng {EV-xxxx})
3. **Đánh đổi**: Tại sao chọn phương án này (ví dụ: hoãn để tránh bốc hơi)
4. **Kết luận**: Hành động tiếp theo

Phong cách:
- Tiếng Việt tự nhiên, dễ hiểu
- Ngắn gọn (3-5 câu)
- Tập trung vào "tại sao" chứ không chỉ "cái gì"

Ví dụ response:
{
    "narrative_template": "Đã lập kế hoạch tưới cho vườn Cam ZONE_A vào lúc {EV-8805} với lượng nước {EV-8804}. Căn cứ trên độ ẩm đất hiện tại là {EV-8803} và bốc thoát hơi nước {EV-8801}. Hoãn tưới đến chiều vì ánh sáng hiện tại ở mức {EV-8802}, tưới ngay sẽ bốc hơi nhiều. Bồn chứa ở mức {EV-8806}, đủ để thực hiện. Bơm ZONE_A {EV-8807} hoạt động bình thường.",
    "evidence_refs": ["EV-8801", "EV-8802", "EV-8803", "EV-8804", "EV-8805", "EV-8806", "EV-8807"],
    "key_tradeoffs": ["Hoãn tưới đến chiều để tránh bốc hơi do ánh sáng cao điểm"]
}"""


class NarrativeAgent:
    """Narrative Agent — generates human-readable explanations."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings):
        self.store = store
        self.ledger = ledger
        self.settings = settings

    def execute(self, session_context: dict) -> dict:
        """Execute Narrative Agent.

        Returns: {narrative, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        action_plan = session_context.get("action_plan")
        findings = session_context.get("findings", [])
        verification_result = session_context.get("verification_result")

        # Build context summary
        context_summary = self._build_context_summary(user_request, action_plan, findings, verification_result)

        user_prompt = f"""Context:
{context_summary}

Nhiệm vụ của bạn:
1. Viết narrative_template giải thích kế hoạch (tiếng Việt)
2. Dùng placeholders {{EV-xxxx}} cho MỌI con số
3. Giải thích đánh đổi (key_tradeoffs)
4. Liệt kê evidence_refs

Trả về JSON theo schema."""

        try:
            result = complete_structured(
                system_prompt=NARRATIVE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=NARRATIVE_RESULT_SCHEMA,
                schema_name="NarrativeResult",
                settings=self.settings,
                temperature=self.settings.llm_temperature_narration,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "narrative": None,
                    "error": f"Narrative Agent LLM failed: {result.error}",
                    "llm_call_metadata": LLMCallMetadata(used=False),
                    "duration_ms": duration_ms,
                }

            # Check for unsourced numbers (ADR-003 enforcement)
            narrative_template = result.parsed["narrative_template"]
            unsourced_numbers = self._detect_unsourced_numbers(narrative_template)

            if unsourced_numbers:
                logger.warning("Narrative contains unsourced numbers: %s", unsourced_numbers)
                # Replace numbers with placeholders (defensive)
                narrative_template = self._sanitize_narrative(narrative_template)

            # Resolve evidence refs to actual values
            resolved_narrative = self._resolve_evidence(
                narrative_template, result.parsed["evidence_refs"]
            )

            # Build evidence table
            evidence_table = self._build_evidence_table(result.parsed["evidence_refs"])

            narrative = Narrative(
                text_vi=resolved_narrative,
                evidence_refs=result.parsed["evidence_refs"],
                key_tradeoffs=result.parsed["key_tradeoffs"],
                evidence_table=evidence_table,
            )

            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "narrative": narrative,
                "llm_call_metadata": LLMCallMetadata(
                    used=True,
                    model=result.model_used,
                    provider=result.provider,
                    duration_ms=duration_ms,
                    prompt_tokens=result.usage.get("prompt_tokens", 0),
                    completion_tokens=result.usage.get("completion_tokens", 0),
                ),
                "duration_ms": duration_ms,
            }

        except Exception as exc:
            logger.error("NarrativeAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "narrative": None,
                "error": f"Exception: {exc}",
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _build_context_summary(self, user_request: str, action_plan, findings: list, verification_result) -> str:
        """Build context summary for LLM."""
        parts = [f"Yêu cầu người dùng: {user_request}"]

        if action_plan:
            parts.append(f"\nAction Plan: {action_plan.schedule_id if hasattr(action_plan, 'schedule_id') else 'N/A'}")
            if hasattr(action_plan, "zone"):
                parts.append(f"Zone: {action_plan.zone}")
            if hasattr(action_plan, "evidence_refs"):
                parts.append(f"Evidence refs: {', '.join(action_plan.evidence_refs)}")

        if findings:
            parts.append(f"\nFindings từ {len(findings)} workers:")
            for f in findings:
                agent_name = f.get("agent_name", "Unknown")
                recommendation = f.get("recommendation", "")
                parts.append(f"- {agent_name}: {recommendation}")

        if verification_result:
            verdict = getattr(verification_result, "verdict", "UNKNOWN")
            parts.append(f"\nVerification: {verdict}")

        return "\n".join(parts)

    def _detect_unsourced_numbers(self, text: str) -> list[str]:
        """Detect numbers not wrapped in {EV-xxxx} placeholders (ADR-003 violation)."""
        # Find all numbers NOT inside {EV-xxxx}
        # Pattern: numbers (int or float) not preceded by {EV-
        pattern = r"(?<!{EV-)\b\d+(?:\.\d+)?\b"
        matches = re.findall(pattern, text)
        return matches

    def _sanitize_narrative(self, text: str) -> str:
        """Replace unsourced numbers with [DATA] placeholder (defensive)."""
        pattern = r"(?<!{EV-)\b\d+(?:\.\d+)?\b"
        return re.sub(pattern, "[DATA]", text)

    def _resolve_evidence(self, template: str, evidence_refs: list[str]) -> str:
        """Resolve {EV-xxxx} placeholders to actual values."""
        resolved = template

        for ev_id in evidence_refs:
            ev = self.ledger.resolve(ev_id)
            if not ev:
                # Evidence not found → keep placeholder
                continue

            # Format: value + unit (if applicable)
            if ev.unit:
                replacement = f"{ev.value_text} {ev.unit}"
            else:
                replacement = ev.value_text

            # Replace {EV-xxxx} with actual value
            resolved = resolved.replace(f"{{{ev_id}}}", replacement)

        return resolved

    def _build_evidence_table(self, evidence_refs: list[str]) -> list[dict]:
        """Build evidence table for UI display."""
        table = []

        for ev_id in evidence_refs:
            ev = self.ledger.resolve(ev_id)
            if not ev:
                continue

            table.append({
                "evidence_id": ev_id,
                "value": ev.value_text,
                "unit": ev.unit,
                "freshness": ev.freshness.value,
                "observed_at": ev.observed_at_iso,
                "source": ev.source,
            })

        return table
