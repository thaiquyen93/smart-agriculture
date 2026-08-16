from agent_core.llm.client import LLMClient
"""Resource Agent — feasibility checking for irrigation plans.

Follows docs/agent-core/02-agents-and-tools.md §B.4.
Role: "Kiểm tra tính khả thi" — checks water balance, pump health, staff availability.
Uses LLM to interpret resource constraints and make go/no-go decisions.
"""
from __future__ import annotations

import json
import logging
import time

from agent_core.config import Settings
from agent_core.evidence.ledger import EvidenceLedger
from agent_core.llm.structured_output import complete_structured
from agent_core.schemas.session import AgentPhase, AgentStatus, LLMCallMetadata
from agent_core.state.store import FarmStateStore
from agent_core.tools import resource
from agent_core.timeutil import to_iso

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

Nhiệm vụ: Kiểm tra tính khả thi của kế hoạch tưới — đủ nước, bơm hoạt động, có nhân lực.

Bạn có 3 tools:
1. **get_water_balance**: Kiểm tra mức nước bồn chứa so với yêu cầu
2. **get_pump_health**: Kiểm tra trạng thái bơm (OPERATIONAL, DEGRADED, FAULT, OFFLINE)
3. **get_staff_roster**: Kiểm tra lịch trực ca nhân viên (M2: mock data)

Luật quan trọng:
- Nếu nước không đủ → is_blocker=True, ready_for_next_stage=False
- Nếu bơm FAULT hoặc OFFLINE → is_blocker=True
- Nếu bơm DEGRADED → cảnh báo nhưng không block
- Không đưa ra con số cụ thể trong summary_vi — chỉ tham chiếu evidence_refs
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
            "summary_vi": "Bơm ZONE_A hoạt động bình thường. Xem {EV-8807}.",
            "evidence_refs": ["EV-8807"],
            "is_blocker": false
        }
    ],
    "recommendation": "Tất cả tài nguyên sẵn sàng. Có thể thực hiện kế hoạch tưới.",
    "ready_for_next_stage": true
}"""


def _resource_tools_to_llm_schemas() -> list[dict]:
    """Convert resource tools to LLM function schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_water_balance",
                "description": "Kiểm tra mức nước bồn chứa so với yêu cầu",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "required_liters": {
                            "type": "number",
                            "description": "Lượng nước yêu cầu (lít)",
                        },
                    },
                    "required": ["required_liters"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_pump_health",
                "description": "Kiểm tra trạng thái bơm",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "Khu vực (ZONE_A, ZONE_B, ...)"},
                    },
                    "required": ["zone"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_staff_roster",
                "description": "Kiểm tra lịch trực ca nhân viên",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_iso": {"type": "string", "description": "Ngày kiểm tra (ISO-8601)"},
                    },
                    "required": ["date_iso"],
                    "additionalProperties": False,
                },
            },
        },
    ]


class ResourceAgent:
    """Resource Agent — feasibility checking."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings, llm_client: LLMClient):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.llm_client = llm_client

    def execute(self, session_context: dict) -> dict:
        """Execute Resource Agent.

        Returns: {findings, recommendation, ready_for_next_stage, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        zone = session_context.get("zone", "ZONE_A")
        required_liters = session_context.get("required_liters", 400.0)  # From Agronomy Agent
        date_iso = session_context.get("date_iso", "2026-08-16")

        # Build tools menu
        tools_menu = _resource_tools_to_llm_schemas()

        # Call LLM with tools
        user_prompt = f"""Yêu cầu người dùng: {user_request}
Khu vực: {zone}
Lượng nước yêu cầu: {required_liters} lít
Ngày: {date_iso}

Nhiệm vụ của bạn:
1. Gọi get_water_balance để kiểm tra đủ nước không
2. Gọi get_pump_health để kiểm tra bơm hoạt động không
3. Gọi get_staff_roster để kiểm tra có nhân lực không (optional)

Nếu có blocker (nước không đủ, bơm hỏng) → ready_for_next_stage=False

Trả về JSON theo schema."""

        try:
            # First LLM call (may request tools)
            result = complete_structured(
                system_prompt=RESOURCE_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=RESOURCE_RESULT_SCHEMA,
                schema_name="ResourceResult",
                client=self.llm_client,
                temperature=self.settings.llm_temperature_analysis,
                tools=tools_menu,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "findings": [],
                    "recommendation": f"Resource Agent LLM failed: {result.error}",
                    "ready_for_next_stage": False,
                    "llm_call_metadata": LLMCallMetadata(used=False),
                    "duration_ms": duration_ms,
                }

            # Check if LLM requested tool calls
            tool_calls = result.raw_response.get("tool_calls", [])

            if tool_calls:
                # Execute tools
                tool_results = self._execute_tools(tool_calls, zone, required_liters, date_iso)

                # Second LLM call with tool results
                tool_results_text = "\n\n".join(
                    [f"Tool: {tr['tool']}\nResult:\n{tr['result']}" for tr in tool_results]
                )

                result = complete_structured(
                    system_prompt=RESOURCE_SYSTEM_PROMPT,
                    user_prompt=f"{user_prompt}\n\nTool Results:\n{tool_results_text}\n\nBây giờ tổng hợp findings.",
                    schema=RESOURCE_RESULT_SCHEMA,
                    schema_name="ResourceResult",
                    client=self.llm_client,
                    temperature=self.settings.llm_temperature_analysis,
                )

                if not result.ok:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return {
                        "findings": [],
                        "recommendation": f"Resource Agent second call failed: {result.error}",
                        "ready_for_next_stage": False,
                        "llm_call_metadata": LLMCallMetadata(used=False),
                        "duration_ms": duration_ms,
                    }

            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": result.parsed["findings"],
                "recommendation": result.parsed["recommendation"],
                "ready_for_next_stage": result.parsed["ready_for_next_stage"],
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
            logger.error("ResourceAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": [],
                "recommendation": f"Exception: {exc}",
                "ready_for_next_stage": False,
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _execute_tools(self, tool_calls: list[dict], zone: str, required_liters: float, date_iso: str) -> list[dict]:
        """Execute tool calls requested by LLM."""
        results = []

        for tc in tool_calls:
            tool_name = tc.get("function", {}).get("name", "")
            tool_args_str = tc.get("function", {}).get("arguments", "{}")

            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                results.append({"tool": tool_name, "result": "ERROR: Invalid JSON arguments"})
                continue

            # Dispatch to appropriate tool
            if tool_name == "get_water_balance":
                result = resource.get_water_balance(
                    self.store,
                    self.ledger,
                    self.settings,
                    required_liters=tool_args.get("required_liters", required_liters),
                )
            elif tool_name == "get_pump_health":
                result = resource.get_pump_health(
                    self.store,
                    self.ledger,
                    self.settings,
                    zone=tool_args.get("zone", zone),
                )
            elif tool_name == "get_staff_roster":
                result = resource.get_staff_roster(
                    self.store,
                    self.ledger,
                    self.settings,
                    date_iso=tool_args.get("date_iso", date_iso),
                )
            else:
                result = {"ok": False, "error": f"Unknown tool: {tool_name}"}

            # Convert result to markdown string for LLM
            if result.get("ok"):
                result_text = result.get("markdown", json.dumps(result, indent=2))
            else:
                result_text = f"ERROR: {result.get('error', 'Unknown error')}"

            results.append({"tool": tool_name, "result": result_text})

        return results
