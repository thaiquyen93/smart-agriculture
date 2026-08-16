"""Resource Agent — feasibility checking for irrigation plans.

Follows docs/agent-core/02-agents-and-tools.md §B.4.
Role: "Kiểm tra tính khả thi" — checks water balance, pump health, staff availability.

Rule 1 (CLAUDE.md — "LLM đề xuất, code định đoạt"): code decides which
tools to call (deterministic, always the same fixed set), executes them
directly, then makes exactly ONE LLM call to turn the tool output into
structured findings — see field_iot_agent.py for the same pattern.
"""
from __future__ import annotations

import json
import logging
import time

from agent_core.config import Settings
from agent_core.devices import ZONE
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.llm.client import LLMClient
from agent_core.llm.structured_output import complete_structured
from agent_core.schemas.session import LLMCallMetadata
from agent_core.state.store import FarmStateStore
from agent_core.timeutil import to_iso
from agent_core.tools import resource

logger = logging.getLogger(__name__)


# Resource Agent output schema (Schema Intersection Rule compliant)
RESOURCE_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_type": {
                        "type": "string",
                        "enum": ["WATER_BALANCE", "PUMP_HEALTH", "STAFF_ROSTER", "FEASIBILITY_CHECK"],
                    },
                    "summary_vi": {"type": "string", "description": "Tóm tắt phát hiện (tiếng Việt)"},
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Danh sách evidence_id (EV-xxxx)",
                    },
                    "is_blocker": {"type": "boolean", "description": "Có phải rào cản không (thiếu nước, bơm hỏng, ...)"},
                },
                "required": ["finding_type", "summary_vi", "evidence_refs", "is_blocker"],
                "additionalProperties": False,
            },
        },
        "recommendation": {"type": "string", "description": "Khuyến nghị về tính khả thi"},
        "ready_for_next_stage": {"type": "boolean", "description": "Có thể thực hiện kế hoạch không (không có blocker)"},
    },
    "required": ["findings", "recommendation", "ready_for_next_stage"],
    "additionalProperties": False,
}


RESOURCE_SYSTEM_PROMPT = """Bạn là Resource Agent trong hệ thống Multi-Agent quản lý nông trại thông minh.

Nhiệm vụ: Đọc kết quả 3 tool đã được code gọi sẵn (get_water_balance, get_pump_health,
get_staff_roster) và kết luận về tính khả thi — đủ nước, bơm hoạt động, có nhân lực.

Luật quan trọng:
- Nếu nước không đủ → is_blocker=True, ready_for_next_stage=False
- Nếu bơm FAULT → is_blocker=True
- Nếu bơm DEGRADED → cảnh báo nhưng không block
- Không đưa ra con số cụ thể trong summary_vi — chỉ tham chiếu evidence_refs đã có trong tool result
- ready_for_next_stage=True CHỈ KHI không có blocker nào

Ví dụ response:
{
    "findings": [
        {
            "finding_type": "WATER_BALANCE",
            "summary_vi": "Bồn chứa đủ nước cho kế hoạch. Xem {EV-8806}.",
            "evidence_refs": ["EV-8806"],
            "is_blocker": false
        },
        {
            "finding_type": "PUMP_HEALTH",
            "summary_vi": "Bơm PUMP_01 hoạt động bình thường. Xem {EV-8807}.",
            "evidence_refs": ["EV-8807"],
            "is_blocker": false
        }
    ],
    "recommendation": "Tất cả tài nguyên sẵn sàng. Có thể thực hiện kế hoạch tưới.",
    "ready_for_next_stage": true
}"""


class ResourceAgent:
    """Resource Agent — feasibility checking."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings, client: LLMClient):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.client = client

    def execute(self, session_context: dict) -> dict:
        """Execute Resource Agent.

        Returns: {findings, recommendation, ready_for_next_stage, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        zone = session_context.get("zone", ZONE)
        required_liters = session_context.get("required_liters", 400.0)  # From Agronomy Agent
        date_iso = session_context.get("date_iso") or to_iso(time.time())

        tool_results = self._run_tools(required_liters, date_iso)
        tool_results_text = "\n\n".join(f"Tool: {tr['tool']}\nResult:\n{tr['result']}" for tr in tool_results)

        user_prompt = f"""Yêu cầu người dùng: {user_request}
Khu vực: {zone}
Lượng nước yêu cầu: {required_liters} lít
Ngày: {date_iso}

Kết quả tool đã chạy:
{tool_results_text}

Nếu có blocker (nước không đủ, bơm hỏng) → ready_for_next_stage=False. Trả về JSON theo schema."""

        try:
            result = complete_structured(
                self.client,
                system_prompt=RESOURCE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=RESOURCE_RESULT_SCHEMA,
                schema_name="ResourceResult",
                temperature=self.settings.llm_temperature_decision,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "findings": [],
                    "recommendation": f"Resource Agent LLM failed: {result.message}",
                    "ready_for_next_stage": False,
                    "llm_call_metadata": LLMCallMetadata(used=False),
                    "duration_ms": duration_ms,
                }

            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": result.data["findings"],
                "recommendation": result.data["recommendation"],
                "ready_for_next_stage": result.data["ready_for_next_stage"],
                "llm_call_metadata": LLMCallMetadata(
                    used=True,
                    model=result.model,
                    provider=result.provider,
                    duration_ms=duration_ms,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                ),
                "duration_ms": duration_ms,
            }

        except Exception as exc:
            logger.error("ResourceAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": [],
                "recommendation": f"Exception: {exc}",
                "ready_for_next_stage": False,
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _run_tools(self, required_liters: float, date_iso: str) -> list[dict]:
        """Deterministically call the fixed Resource tool set."""
        results = []

        water_balance = resource.get_water_balance(self.store, self.ledger, self.settings, required_liters=required_liters)
        pump_health = resource.get_pump_health(self.store, self.ledger, self.settings, pump_id="PUMP_01")
        staff_roster = resource.get_staff_roster(self.store, self.ledger, self.settings, date_iso=date_iso)

        for tool_name, tool_result in [
            ("get_water_balance", water_balance),
            ("get_pump_health", pump_health),
            ("get_staff_roster", staff_roster),
        ]:
            if tool_result.get("ok"):
                result_text = tool_result.get("markdown", json.dumps(tool_result, indent=2))
            else:
                result_text = f"ERROR: {tool_result.get('message', 'Unknown error')}"
            results.append({"tool": tool_name, "result": result_text})

        return results
