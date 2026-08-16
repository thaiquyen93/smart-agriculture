from agent_core.llm.client import LLMClient
"""Farm Coordinator Agent — orchestrates worker dispatch and ready_to_act decision.

Follows docs/agent-core/02-agents-and-tools.md §B.7.
Role: Tổng hợp findings từ workers, quyết định ready_to_act.
Uses LLM to judge whether workers have collected enough information to proceed.
"""
from __future__ import annotations

import logging
import time

from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.llm.structured_output import complete_structured
from agent_core.schemas.session import AgentPhase, AgentStatus, LLMCallMetadata
from agent_core.state.store import FarmStateStore

logger = logging.getLogger(__name__)


# Coordinator output schema (Schema Intersection Rule compliant)
COORDINATOR_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "ready_to_act": {
            "type": "boolean",
            "description": "Có đủ thông tin để chuyển sang Action Agent không",
        },
        "reasoning": {
            "type": "string",
            "description": "Lý do quyết định ready_to_act",
        },
        "missing_information": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Thông tin còn thiếu (nếu ready_to_act=False)",
        },
        "next_workers": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["FieldIoT", "Agronomy", "Resource"],
            },
            "description": "Workers cần gọi ở round tiếp theo (nếu ready_to_act=False)",
        },
    },
    "required": ["ready_to_act", "reasoning", "missing_information"],
    "additionalProperties": False,
}


COORDINATOR_SYSTEM_PROMPT = """Bạn là Farm Coordinator Agent trong hệ thống Multi-Agent quản lý nông trại thông minh.

Nhiệm vụ: Tổng hợp findings từ workers (Field IoT, Agronomy, Resource), quyết định có đủ thông tin để chuyển sang Action Agent không.

Luật quyết định ready_to_act:
1. **ready_to_act=True** NẾU:
   - Field IoT: dữ liệu FRESH, đã lấy snapshot
   - Agronomy: đã ước tính lượng nước cần tưới, có recommendation về timing
   - Resource: xác nhận đủ nước, bơm hoạt động
   - TẤT CẢ 3 workers có ready_for_next_stage=True

2. **ready_to_act=False** NẾU:
   - Thiếu dữ liệu quan trọng (không có ET0, không biết lượng nước, bơm chưa check)
   - Có blocker từ Resource (nước không đủ, bơm hỏng)
   - Dữ liệu STALE hoặc OFFLINE từ Field IoT

3. **Bounded Orchestration (ADR-002)**:
   - Sau 2 rounds mà vẫn chưa ready → ĐI TIẾP với state=PARTIAL
   - Không được lặp vô hạn

Trả về:
- ready_to_act: true/false
- reasoning: giải thích quyết định
- missing_information: danh sách thông tin thiếu (nếu False)
- next_workers: workers cần gọi ở round tiếp theo (nếu False)

Ví dụ response (ready=True):
{
    "ready_to_act": true,
    "reasoning": "3 workers đã thu thập đủ thông tin: dữ liệu FRESH, nhu cầu nước 412L, tài nguyên đủ.",
    "missing_information": []
}

Ví dụ response (ready=False):
{
    "ready_to_act": false,
    "reasoning": "Agronomy Agent chưa ước tính lượng nước cần tưới. Cần thêm 1 round.",
    "missing_information": ["Ước tính lượng nước cần tưới (water_demand)"],
    "next_workers": ["Agronomy"]
}"""


class CoordinatorAgent:
    """Farm Coordinator Agent — orchestration and ready_to_act decision."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings, llm_client: LLMClient):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.llm_client = llm_client

    def execute(self, session_context: dict) -> dict:
        """Execute Coordinator Agent.

        Returns: {ready_to_act, reasoning, missing_information, next_workers, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        findings = session_context.get("findings", [])
        current_round = session_context.get("current_round", 1)
        max_rounds = self.settings.agent_max_dispatch_rounds

        # Build findings summary
        findings_summary = self._summarize_findings(findings)

        user_prompt = f"""Yêu cầu người dùng: {user_request}

Findings từ workers (Round {current_round}/{max_rounds}):
{findings_summary}

Nhiệm vụ của bạn:
1. Phân tích findings từ workers
2. Quyết định ready_to_act (có đủ thông tin để Action Agent tạo plan không)
3. Nếu False → liệt kê missing_information và next_workers

Luật quan trọng:
- Sau {max_rounds} rounds mà vẫn chưa ready → vẫn trả về ready_to_act=True với lý do "Bounded orchestration — đi tiếp với thông tin hiện có"

Trả về JSON theo schema."""

        try:
            result = complete_structured(
                system_prompt=COORDINATOR_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=COORDINATOR_RESULT_SCHEMA,
                schema_name="CoordinatorResult",
                client=self.llm_client,
                temperature=self.settings.llm_temperature_decision,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                # Fallback: check if all workers reported ready_for_next_stage=True
                all_ready = all(f.get("ready_for_next_stage", False) for f in findings)
                return {
                    "ready_to_act": all_ready,
                    "reasoning": f"Coordinator LLM failed: {result.error}. Fallback: all_workers_ready={all_ready}",
                    "missing_information": [] if all_ready else ["LLM unavailable"],
                    "next_workers": [] if all_ready else ["FieldIoT", "Agronomy", "Resource"],
                    "llm_call_metadata": LLMCallMetadata(used=False),
                    "duration_ms": duration_ms,
                }

            # Enforce bounded orchestration (ADR-002)
            ready_to_act = result.parsed["ready_to_act"]
            if current_round >= max_rounds and not ready_to_act:
                logger.warning(
                    "Bounded orchestration: max rounds (%d) reached, forcing ready_to_act=True",
                    max_rounds,
                )
                ready_to_act = True
                result.parsed["reasoning"] += f" [Bounded orchestration — đã hết {max_rounds} rounds, đi tiếp]"

            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "ready_to_act": ready_to_act,
                "reasoning": result.parsed["reasoning"],
                "missing_information": result.parsed["missing_information"],
                "next_workers": result.parsed.get("next_workers", []),
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
            logger.error("CoordinatorAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "ready_to_act": False,
                "reasoning": f"Exception: {exc}",
                "missing_information": ["Coordinator crashed"],
                "next_workers": [],
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _summarize_findings(self, findings: list[dict]) -> str:
        """Summarize findings from workers into text for LLM."""
        if not findings:
            return "Chưa có findings nào từ workers."

        summary_parts = []
        for finding in findings:
            agent_name = finding.get("agent_name", "Unknown")
            recommendation = finding.get("recommendation", "N/A")
            ready = finding.get("ready_for_next_stage", False)
            evidence_refs = finding.get("evidence_refs", [])

            # Check for blockers (Resource Agent)
            is_blocker = any(
                f.get("is_blocker", False)
                for f in finding.get("findings", [])
            )

            status_icon = "✅" if ready else "⏳"
            blocker_icon = "🚫" if is_blocker else ""

            summary_parts.append(
                f"{status_icon} {blocker_icon} **{agent_name}**:\n"
                f"  - Recommendation: {recommendation}\n"
                f"  - Ready: {ready}\n"
                f"  - Evidence: {len(evidence_refs)} refs"
            )

        return "\n\n".join(summary_parts)
