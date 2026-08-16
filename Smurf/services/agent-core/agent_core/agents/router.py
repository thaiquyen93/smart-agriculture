"""Router Agent — classifies user requests into 5 playbooks.

Follows docs/agent-core/02-agents-and-tools.md §B.1.
Has heuristic fallback when LLM fails (keywords-based).
"""
from __future__ import annotations

import logging
import time

from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.llm.structured_output import complete_structured
from agent_core.schemas.session import AgentPhase, AgentStatus, LLMCallMetadata, Playbook
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso

logger = logging.getLogger(__name__)


# Router output schema (Schema Intersection Rule compliant)
ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "playbook": {
            "type": "string",
            "enum": ["PLAN_IRRIGATION", "INSPECT_SESSION", "DEVICE_ISSUE", "REPORT", "ASK_DATA"],
            "description": "Playbook được chọn",
        },
        "zone": {"type": "string", "description": "Tên khu vực (nếu có, ví dụ: ZONE_A)"},
        "reasoning": {"type": "string", "description": "Lý do chọn playbook này"},
    },
    "required": ["playbook", "zone", "reasoning"],
    "additionalProperties": False,
}


ROUTER_SYSTEM_PROMPT = """Bạn là Router Agent trong hệ thống Multi-Agent quản lý nông trại thông minh.

Nhiệm vụ: Phân loại yêu cầu người dùng vào 1 trong 5 playbook:

1. **PLAN_IRRIGATION**: Lập kế hoạch tưới (từ khoá: "tưới", "nước", "lập kế hoạch", "irrigation", "watering")
2. **INSPECT_SESSION**: Kiểm tra phiên tưới đã thực hiện (từ khoá: "kiểm tra", "xem lại", "inspect", "review")
3. **DEVICE_ISSUE**: Xử lý sự cố thiết bị (từ khoá: "lỗi", "hỏng", "mất kết nối", "offline", "fault")
4. **REPORT**: Tạo báo cáo tổng hợp (từ khoá: "báo cáo", "thống kê", "report", "summary")
5. **ASK_DATA**: Tra cứu dữ liệu cảm biến (từ khoá: "độ ẩm", "nhiệt độ", "dữ liệu", "sensor data")

Luật:
- Nếu không rõ, ưu tiên PLAN_IRRIGATION (đây là playbook mặc định)
- Trích xuất tên khu vực (ZONE_A, ZONE_B, ...) nếu có trong yêu cầu
- Nếu không có tên khu vực, điền "ZONE_A" (mặc định)

Trả về JSON có 3 trường: playbook, zone, reasoning."""


def heuristic_fallback(user_request: str) -> dict:
    """Keyword-based fallback when LLM fails.

    Returns: {playbook, zone, reasoning}
    """
    request_lower = user_request.lower()

    # Keyword rules
    if any(kw in request_lower for kw in ["tưới", "nước", "lập kế hoạch", "irrigation", "watering"]):
        playbook = "PLAN_IRRIGATION"
    elif any(kw in request_lower for kw in ["kiểm tra", "xem lại", "inspect", "review"]):
        playbook = "INSPECT_SESSION"
    elif any(kw in request_lower for kw in ["lỗi", "hỏng", "mất kết nối", "offline", "fault"]):
        playbook = "DEVICE_ISSUE"
    elif any(kw in request_lower for kw in ["báo cáo", "thống kê", "report", "summary"]):
        playbook = "REPORT"
    elif any(kw in request_lower for kw in ["độ ẩm", "nhiệt độ", "dữ liệu", "sensor", "data"]):
        playbook = "ASK_DATA"
    else:
        # Default: PLAN_IRRIGATION
        playbook = "PLAN_IRRIGATION"

    # Extract zone
    zone = "ZONE_A"  # Default
    if "zone" in request_lower:
        # Simple extraction: "zone_a", "zone a", "khu a"
        if "a" in request_lower:
            zone = "ZONE_A"
        elif "b" in request_lower:
            zone = "ZONE_B"

    return {
        "playbook": playbook,
        "zone": zone,
        "reasoning": f"Heuristic fallback dựa trên từ khoá. LLM không khả dụng.",
    }


class RouterAgent:
    """Router Agent — request classification."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings):
        self.store = store
        self.ledger = ledger
        self.settings = settings

    def execute(self, user_request: str) -> dict:
        """Classify user request into playbook.

        Returns: {playbook, zone, reasoning, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        try:
            # Try LLM first
            result = complete_structured(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                user_prompt=f"Yêu cầu: {user_request}",
                schema=ROUTER_SCHEMA,
                schema_name="RouterResult",
                settings=self.settings,
                temperature=self.settings.llm_temperature_decision,
            )

            if result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "playbook": Playbook(result.parsed["playbook"]),
                    "zone": result.parsed["zone"],
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
            else:
                # LLM failed → fallback
                logger.warning("Router LLM failed: %s. Using heuristic fallback.", result.error)
                fallback_result = heuristic_fallback(user_request)
                duration_ms = int((time.time() - start_time) * 1000)

                return {
                    "playbook": Playbook(fallback_result["playbook"]),
                    "zone": fallback_result["zone"],
                    "reasoning": fallback_result["reasoning"],
                    "llm_call_metadata": LLMCallMetadata(used=False),  # Code-only fallback
                    "duration_ms": duration_ms,
                }

        except Exception as exc:
            logger.error("Router execute failed: %s", exc, exc_info=True)
            # Final fallback
            fallback_result = heuristic_fallback(user_request)
            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "playbook": Playbook(fallback_result["playbook"]),
                "zone": fallback_result["zone"],
                "reasoning": f"Exception fallback: {exc}",
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }
