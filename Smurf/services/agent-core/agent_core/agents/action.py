"""Farm Action Agent — creates executable action plans.

Follows docs/agent-core/02-agents-and-tools.md §B.5.
Role: "Điền action schemas" — fills IrrigationSchedule, InspectionTicket, etc.
Uses LLM to synthesize findings from workers into concrete action plans.
"""
from __future__ import annotations

import json
import logging
import time

from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.llm.structured_output import complete_structured
from agent_core.schemas.action import IrrigationSchedule, InspectionTicket, Notification, Report
from agent_core.schemas.session import AgentPhase, AgentStatus, LLMCallMetadata
from agent_core.state.store import FarmStateStore
from agent_core.tools import action
from agent_core.timeutil import to_iso

logger = logging.getLogger(__name__)


# Action Agent output schema (Schema Intersection Rule compliant)
ACTION_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "action_type": {
            "type": "string",
            "enum": ["IRRIGATION_SCHEDULE", "INSPECTION_TICKET", "NOTIFICATION", "REPORT"],
            "description": "Loại hành động cần thực hiện",
        },
        "action_params": {
            "type": "object",
            "description": "Tham số cho action tool (sẽ được truyền vào create_* function)",
            "properties": {
                "zone": {"type": "string"},
                "start_time_iso": {"type": "string"},
                "duration_minutes": {"type": "integer"},
                "target_volume_liters": {"type": "number"},
                "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"]},
                "reason_vi": {"type": "string"},
                "confidence": {"type": "string", "enum": ["CONFIDENT", "TENTATIVE", "UNCERTAIN"]},
                "mode": {"type": "string", "enum": ["FULL", "PARTIAL", "SKIP"]},
            },
            "required": ["zone", "start_time_iso", "duration_minutes", "target_volume_liters", "reason_vi"],
            "additionalProperties": True,  # Allow extra fields for other action types
        },
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tất cả evidence_refs từ workers (để Policy Gate audit)",
        },
        "reasoning": {"type": "string", "description": "Lý do chọn action này"},
    },
    "required": ["action_type", "action_params", "evidence_refs", "reasoning"],
    "additionalProperties": False,
}


ACTION_SYSTEM_PROMPT = """Bạn là Farm Action Agent trong hệ thống Multi-Agent quản lý nông trại thông minh.

Nhiệm vụ: Tổng hợp findings từ 3 workers (Field IoT, Agronomy, Resource) thành action plan cụ thể.

Bạn KHÔNG gọi tools trực tiếp. Bạn chỉ trả về JSON với:
- action_type: loại action (IRRIGATION_SCHEDULE là phổ biến nhất)
- action_params: tham số để tạo action (zone, start_time_iso, duration_minutes, target_volume_liters, priority, reason_vi, confidence, mode)
- evidence_refs: tất cả evidence_id từ workers (để truy vết)
- reasoning: giải thích tại sao chọn action này

Luật quan trọng:
- Dựa trên findings từ 3 workers, tổng hợp thành 1 action duy nhất
- start_time_iso: phải có timezone (ví dụ: 2026-08-16T16:30:00+07:00)
- duration_minutes: dựa trên target_volume_liters và flow rate (giả sử ~15L/phút)
- priority: HIGH nếu độ ẩm đất thấp, MEDIUM nếu bình thường
- confidence: CONFIDENT nếu 3 workers đều ready_for_next_stage=True
- mode: FULL (tưới đủ), PARTIAL (tưới 1 phần), SKIP (hoãn)
- reason_vi: giải thích ngắn gọn tại sao cần tưới (tiếng Việt)
- Tập hợp TẤT CẢ evidence_refs từ findings của 3 workers

Ví dụ response:
{
    "action_type": "IRRIGATION_SCHEDULE",
    "action_params": {
        "zone": "ZONE_A",
        "start_time_iso": "2026-08-16T16:30:00+07:00",
        "duration_minutes": 28,
        "target_volume_liters": 412.0,
        "priority": "HIGH",
        "reason_vi": "Độ ẩm đất thấp, cần bù nước theo ET0. Hoãn đến chiều để tránh bốc hơi.",
        "confidence": "CONFIDENT",
        "mode": "FULL"
    },
    "evidence_refs": ["EV-8801", "EV-8802", "EV-8803", "EV-8804", "EV-8805", "EV-8806", "EV-8807"],
    "reasoning": "3 workers xác nhận: dữ liệu tươi, nhu cầu nước 412L, tài nguyên đủ. Lập kế hoạch tưới đầy đủ."
}"""


class ActionAgent:
    """Farm Action Agent — synthesizes findings into action plans."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings):
        self.store = store
        self.ledger = ledger
        self.settings = settings

    def execute(self, session_context: dict) -> dict:
        """Execute Action Agent.

        Returns: {action_plan, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        session_id = session_context.get("session_id", "")
        findings = session_context.get("findings", [])  # From workers

        # Build context from findings
        findings_summary = self._summarize_findings(findings)

        user_prompt = f"""Yêu cầu người dùng: {user_request}

Findings từ 3 workers:
{findings_summary}

Nhiệm vụ của bạn:
- Tổng hợp findings thành 1 action plan cụ thể
- Chọn action_type (IRRIGATION_SCHEDULE là phổ biến nhất)
- Điền action_params với đầy đủ thông tin
- Thu thập TẤT CẢ evidence_refs từ findings

Trả về JSON theo schema."""

        try:
            result = complete_structured(
                system_prompt=ACTION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=ACTION_RESULT_SCHEMA,
                schema_name="ActionResult",
                settings=self.settings,
                temperature=self.settings.llm_temperature_decision,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "action_plan": None,
                    "error": f"Action Agent LLM failed: {result.error}",
                    "llm_call_metadata": LLMCallMetadata(used=False),
                    "duration_ms": duration_ms,
                }

            # Convert LLM output to actual action plan
            action_type = result.parsed["action_type"]
            action_params = result.parsed["action_params"]
            evidence_refs = result.parsed["evidence_refs"]

            action_plan = None

            if action_type == "IRRIGATION_SCHEDULE":
                # Call action tool to create plan (with idempotency)
                idempotency_key = f"{session_id}-irrigation"
                tool_result = action.create_irrigation_schedule(
                    self.store,
                    self.ledger,
                    self.settings,
                    session_id=session_id,
                    zone=action_params["zone"],
                    start_time_iso=action_params["start_time_iso"],
                    duration_minutes=action_params["duration_minutes"],
                    target_volume_liters=action_params["target_volume_liters"],
                    priority=action_params.get("priority", "MEDIUM"),
                    reason_vi=action_params["reason_vi"],
                    confidence=action_params.get("confidence", "CONFIDENT"),
                    mode=action_params.get("mode", "FULL"),
                    evidence_refs=evidence_refs,
                    idempotency_key=idempotency_key,
                )

                if tool_result["ok"]:
                    action_plan = tool_result["schedule"]
                else:
                    logger.error("create_irrigation_schedule failed: %s", tool_result.get("error"))

            elif action_type == "INSPECTION_TICKET":
                idempotency_key = f"{session_id}-inspection"
                tool_result = action.create_inspection_ticket(
                    self.store,
                    self.ledger,
                    self.settings,
                    session_id=session_id,
                    zone=action_params.get("zone", "ZONE_A"),
                    issue_type=action_params.get("issue_type", "SENSOR_OFFLINE"),
                    description_vi=action_params.get("description_vi", "Cần kiểm tra"),
                    priority=action_params.get("priority", "MEDIUM"),
                    evidence_refs=evidence_refs,
                    idempotency_key=idempotency_key,
                )

                if tool_result["ok"]:
                    action_plan = tool_result["ticket"]

            # Add more action types as needed (NOTIFICATION, REPORT)

            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "action_plan": action_plan,
                "reasoning": result.parsed["reasoning"],
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
            logger.error("ActionAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "action_plan": None,
                "error": f"Exception: {exc}",
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _summarize_findings(self, findings: list[dict]) -> str:
        """Summarize findings from workers into text for LLM."""
        if not findings:
            return "Không có findings nào từ workers."

        summary_parts = []
        for i, finding in enumerate(findings):
            agent_name = finding.get("agent_name", f"Worker {i+1}")
            recommendation = finding.get("recommendation", "")
            ready = finding.get("ready_for_next_stage", False)
            evidence_refs = finding.get("evidence_refs", [])

            summary_parts.append(
                f"**{agent_name}**:\n"
                f"- Recommendation: {recommendation}\n"
                f"- Ready: {ready}\n"
                f"- Evidence: {', '.join(evidence_refs)}"
            )

        return "\n\n".join(summary_parts)
