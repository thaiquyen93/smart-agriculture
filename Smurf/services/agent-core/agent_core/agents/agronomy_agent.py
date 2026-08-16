from agent_core.llm.client import LLMClient
"""Agronomy Agent — crop science and water demand estimation.

Follows docs/agent-core/02-agents-and-tools.md §B.3.
Role: "Phán đoán nông học" — agronomic judgment (no raw calculation).
Uses LLM to interpret agronomy tools and make recommendations.
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
from agent_core.tools import agronomy
from agent_core.timeutil import to_iso

logger = logging.getLogger(__name__)


# Agronomy Agent output schema (Schema Intersection Rule compliant)
AGRONOMY_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_type": {
                        "type": "string",
                        "enum": ["ET0_ESTIMATE", "WATER_DEMAND", "SOIL_MOISTURE_FORECAST", "TIMING_RECOMMENDATION"],
                    },
                    "summary_vi": {"type": "string", "description": "Tóm tắt phát hiện (tiếng Việt)"},
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Danh sách evidence_id (EV-xxxx)",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["HIGH", "MEDIUM", "LOW"],
                        "description": "Độ tin cậy của phán đoán",
                    },
                },
                "required": ["finding_type", "summary_vi", "evidence_refs", "confidence"],
                "additionalProperties": False,
            },
        },
        "recommendation": {"type": "string", "description": "Khuyến nghị nông học"},
        "ready_for_next_stage": {"type": "boolean", "description": "Có đủ thông tin để lập kế hoạch không"},
    },
    "required": ["findings", "recommendation", "ready_for_next_stage"],
    "additionalProperties": False,
}


AGRONOMY_SYSTEM_PROMPT = """Bạn là Agronomy Agent trong hệ thống Multi-Agent quản lý nông trại thông minh.

Nhiệm vụ: Phán đoán nông học dựa trên dữ liệu thời tiết, độ ẩm đất, và nhu cầu nước của cây trồng.

Bạn có 3 tools:
1. **estimate_et0**: Ước tính bốc thoát hơi nước tiềm năng (ET0) theo Penman-Monteith đơn giản hóa
2. **estimate_water_demand**: Ước tính lượng nước cần tưới dựa trên ET0 và độ thiếu hụt đất
3. **forecast_soil_moisture**: Dự báo độ ẩm đất sau N giờ (dựa trên vật lý suy giảm)

Luật quan trọng:
- Không tự tính toán số liệu — luôn gọi tools để lấy con số
- Xem xét đánh đổi: tưới ngay vs hoãn (vì nhiệt độ, ánh sáng cao điểm)
- Không đưa ra con số cụ thể trong summary_vi — chỉ tham chiếu evidence_refs
- Confidence: HIGH nếu dữ liệu đầy đủ + thời tiết ổn định, MEDIUM nếu thiếu dữ liệu, LOW nếu thời tiết biến động
- ready_for_next_stage=True nếu đã ước tính được lượng nước cần tưới

Ví dụ response:
{
    "findings": [
        {
            "finding_type": "WATER_DEMAND",
            "summary_vi": "Ước tính nhu cầu nước dựa trên ET0 và độ thiếu hụt đất. Xem {EV-8804}.",
            "evidence_refs": ["EV-8804"],
            "confidence": "HIGH"
        },
        {
            "finding_type": "TIMING_RECOMMENDATION",
            "summary_vi": "Khuyến nghị hoãn tưới tới 16:30 vì lux đang ở đỉnh. Xem {EV-8805}.",
            "evidence_refs": ["EV-8805"],
            "confidence": "MEDIUM"
        }
    ],
    "recommendation": "Cần tưới trong ngày. Hoãn đến chiều để tránh bốc hơi cao.",
    "ready_for_next_stage": true
}"""


def _agronomy_tools_to_llm_schemas() -> list[dict]:
    """Convert agronomy tools to LLM function schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": "estimate_et0",
                "description": "Ước tính bốc thoát hơi nước tiềm năng (ET0) theo Penman-Monteith đơn giản",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "Khu vực (ZONE_A, ZONE_B, ...)"},
                        "date_iso": {"type": "string", "description": "Ngày tính ET0 (ISO-8601, ví dụ: 2026-08-16)"},
                    },
                    "required": ["zone", "date_iso"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "estimate_water_demand",
                "description": "Ước tính lượng nước cần tưới dựa trên ET0 và độ thiếu hụt đất",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "Khu vực"},
                        "date_iso": {"type": "string", "description": "Ngày"},
                        "crop_type": {"type": "string", "description": "Loại cây trồng (ví dụ: cam, chanh)"},
                    },
                    "required": ["zone", "date_iso", "crop_type"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "forecast_soil_moisture",
                "description": "Dự báo độ ẩm đất sau N giờ (vật lý suy giảm)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "Khu vực"},
                        "hours_ahead": {"type": "integer", "description": "Số giờ dự báo (1-48)"},
                    },
                    "required": ["zone", "hours_ahead"],
                    "additionalProperties": False,
                },
            },
        },
    ]


class AgronomyAgent:
    """Agronomy Agent — crop science and water demand estimation."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings, llm_client: LLMClient):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.llm_client = llm_client

    def execute(self, session_context: dict) -> dict:
        """Execute Agronomy Agent.

        Returns: {findings, recommendation, ready_for_next_stage, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        zone = session_context.get("zone", "ZONE_A")
        crop_type = session_context.get("crop_type", "cam")  # Default: orange
        date_iso = session_context.get("date_iso", "2026-08-16")

        # Build tools menu
        tools_menu = _agronomy_tools_to_llm_schemas()

        # Call LLM with tools
        user_prompt = f"""Yêu cầu người dùng: {user_request}
Khu vực: {zone}
Loại cây trồng: {crop_type}
Ngày: {date_iso}

Nhiệm vụ của bạn:
1. Gọi estimate_et0 để ước tính bốc thoát hơi nước
2. Gọi estimate_water_demand để tính lượng nước cần tưới
3. Nếu cần dự báo → gọi forecast_soil_moisture
4. Xem xét timing: nên tưới ngay hay hoãn (vì nhiệt độ, ánh sáng)

Trả về JSON theo schema."""

        try:
            # First LLM call (may request tools)
            result = complete_structured(
                system_prompt=AGRONOMY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=AGRONOMY_RESULT_SCHEMA,
                schema_name="AgronomyResult",
                client=self.llm_client,
                temperature=self.settings.llm_temperature_analysis,
                tools=tools_menu,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "findings": [],
                    "recommendation": f"Agronomy Agent LLM failed: {result.error}",
                    "ready_for_next_stage": False,
                    "llm_call_metadata": LLMCallMetadata(used=False),
                    "duration_ms": duration_ms,
                }

            # Check if LLM requested tool calls
            tool_calls = result.raw_response.get("tool_calls", [])

            if tool_calls:
                # Execute tools
                tool_results = self._execute_tools(tool_calls, zone, crop_type, date_iso)

                # Second LLM call with tool results
                tool_results_text = "\n\n".join(
                    [f"Tool: {tr['tool']}\nResult:\n{tr['result']}" for tr in tool_results]
                )

                result = complete_structured(
                    system_prompt=AGRONOMY_SYSTEM_PROMPT,
                    user_prompt=f"{user_prompt}\n\nTool Results:\n{tool_results_text}\n\nBây giờ tổng hợp findings.",
                    schema=AGRONOMY_RESULT_SCHEMA,
                    schema_name="AgronomyResult",
                    client=self.llm_client,
                    temperature=self.settings.llm_temperature_analysis,
                )

                if not result.ok:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return {
                        "findings": [],
                        "recommendation": f"Agronomy Agent second call failed: {result.error}",
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
            logger.error("AgronomyAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": [],
                "recommendation": f"Exception: {exc}",
                "ready_for_next_stage": False,
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _execute_tools(self, tool_calls: list[dict], zone: str, crop_type: str, date_iso: str) -> list[dict]:
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
            if tool_name == "estimate_et0":
                result = agronomy.estimate_et0(
                    self.store,
                    self.ledger,
                    self.settings,
                    zone=tool_args.get("zone", zone),
                    date_iso=tool_args.get("date_iso", date_iso),
                )
            elif tool_name == "estimate_water_demand":
                result = agronomy.estimate_water_demand(
                    self.store,
                    self.ledger,
                    self.settings,
                    zone=tool_args.get("zone", zone),
                    date_iso=tool_args.get("date_iso", date_iso),
                    crop_type=tool_args.get("crop_type", crop_type),
                )
            elif tool_name == "forecast_soil_moisture":
                result = agronomy.forecast_soil_moisture(
                    self.store,
                    self.ledger,
                    self.settings,
                    zone=tool_args.get("zone", zone),
                    hours_ahead=tool_args.get("hours_ahead", 4),
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
