from agent_core.llm.client import LLMClient
"""Field IoT Agent — wrapper around 4 M1 Field IoT tools.

Follows docs/agent-core/02-agents-and-tools.md §B.2.
Role: "Gác cổng độ mới dữ liệu" — guards data freshness.
Uses LLM to decide which tools to call, then executes them.
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
from agent_core.tools import field_iot
from agent_core.timeutil import to_iso

logger = logging.getLogger(__name__)


# Field IoT Agent output schema (Schema Intersection Rule compliant)
FIELD_IOT_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "finding_type": {
                        "type": "string",
                        "enum": ["DEVICE_STATUS", "METRIC_SERIES", "FRESHNESS_REPORT", "ANOMALY_REPORT"],
                    },
                    "summary_vi": {"type": "string", "description": "Tóm tắt phát hiện (tiếng Việt)"},
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Danh sách evidence_id (EV-xxxx)",
                    },
                    "freshness_ok": {"type": "boolean", "description": "Dữ liệu có đủ tươi không"},
                },
                "required": ["finding_type", "summary_vi", "evidence_refs", "freshness_ok"],
                "additionalProperties": False,
            },
        },
        "recommendation": {"type": "string", "description": "Khuyến nghị cho coordinator"},
        "ready_for_next_stage": {"type": "boolean", "description": "Có thể chuyển sang agent khác không"},
    },
    "required": ["findings", "recommendation", "ready_for_next_stage"],
    "additionalProperties": False,
}


FIELD_IOT_SYSTEM_PROMPT = """Bạn là Field IoT Agent trong hệ thống Multi-Agent quản lý nông trại thông minh.

Nhiệm vụ: Thu thập dữ liệu cảm biến thời gian thực, kiểm tra độ tươi và chất lượng dữ liệu.

Bạn có 4 tools:
1. **get_device_snapshot**: Lấy snapshot hiện tại của thiết bị (temp, humidity, soil_moisture, lux, tank_level, pump_status)
2. **get_metric_series**: Lấy chuỗi dữ liệu lịch sử (time-series) của thiết bị
3. **get_freshness_report**: Kiểm tra độ tươi của dữ liệu (FRESH, STALE, OFFLINE)
4. **get_anomaly_report**: Phát hiện bất thường trong dữ liệu

Luật quan trọng:
- Luôn kiểm tra độ tươi dữ liệu TRƯỚC KHI sử dụng
- Nếu dữ liệu STALE (>5 phút) hoặc OFFLINE → cảnh báo ngay, đặt freshness_ok=False
- Không đưa ra con số cụ thể trong summary_vi — chỉ tham chiếu evidence_refs
- Trả về JSON có 3 trường: findings, recommendation, ready_for_next_stage
- ready_for_next_stage=True nếu đã có đủ dữ liệu tươi cho agent tiếp theo

Ví dụ response:
{
    "findings": [
        {
            "finding_type": "DEVICE_STATUS",
            "summary_vi": "Đã lấy snapshot 6 thiết bị. Xem {EV-8801} để biết chi tiết.",
            "evidence_refs": ["EV-8801"],
            "freshness_ok": true
        },
        {
            "finding_type": "FRESHNESS_REPORT",
            "summary_vi": "Tất cả thiết bị FRESH (< 2 phút). Xem {EV-8802}.",
            "evidence_refs": ["EV-8802"],
            "freshness_ok": true
        }
    ],
    "recommendation": "Dữ liệu đã sẵn sàng. Có thể chuyển sang Agronomy Agent.",
    "ready_for_next_stage": true
}"""


class FieldIoTAgent:
    """Field IoT Agent — data collection and freshness gating."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings, llm_client: LLMClient):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.llm_client = llm_client

    def execute(self, session_context: dict) -> dict:
        """Execute Field IoT Agent.

        Returns: {findings, recommendation, ready_for_next_stage, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        zone = session_context.get("zone", "ZONE_A")

        # Build tools menu
        tools_menu = field_iot.to_llm_tool_schemas()

        # Call LLM with tools (manual tool-calling loop)
        user_prompt = f"""Yêu cầu người dùng: {user_request}
Khu vực: {zone}

Nhiệm vụ của bạn:
1. Gọi get_freshness_report để kiểm tra độ tươi dữ liệu
2. Nếu FRESH → gọi get_device_snapshot lấy snapshot hiện tại
3. Nếu cần lịch sử → gọi get_metric_series
4. Nếu có dấu hiệu bất thường → gọi get_anomaly_report

Trả về JSON theo schema."""

        try:
            # First LLM call (may request tools)
            result = complete_structured(
                system_prompt=FIELD_IOT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=FIELD_IOT_RESULT_SCHEMA,
                schema_name="FieldIoTResult",
                client=self.llm_client,
                temperature=self.settings.llm_temperature_analysis,
                tools=tools_menu,
            )

            if not result.ok:
                # LLM failed → return minimal result
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "findings": [],
                    "recommendation": f"Field IoT Agent LLM failed: {result.error}",
                    "ready_for_next_stage": False,
                    "llm_call_metadata": LLMCallMetadata(used=False),
                    "duration_ms": duration_ms,
                }

            # Check if LLM requested tool calls
            tool_calls = result.raw_response.get("tool_calls", [])

            if tool_calls:
                # Execute tools
                tool_results = self._execute_tools(tool_calls, zone)

                # Second LLM call with tool results
                tool_results_text = "\n\n".join(
                    [f"Tool: {tr['tool']}\nResult:\n{tr['result']}" for tr in tool_results]
                )

                result = complete_structured(
                    system_prompt=FIELD_IOT_SYSTEM_PROMPT,
                    user_prompt=f"{user_prompt}\n\nTool Results:\n{tool_results_text}\n\nBây giờ tổng hợp findings.",
                    schema=FIELD_IOT_RESULT_SCHEMA,
                    schema_name="FieldIoTResult",
                    client=self.llm_client,
                    temperature=self.settings.llm_temperature_analysis,
                )

                if not result.ok:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return {
                        "findings": [],
                        "recommendation": f"Field IoT Agent second call failed: {result.error}",
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
            logger.error("FieldIoTAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": [],
                "recommendation": f"Exception: {exc}",
                "ready_for_next_stage": False,
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _execute_tools(self, tool_calls: list[dict], zone: str) -> list[dict]:
        """Execute tool calls requested by LLM.

        Returns: [{tool, result}]
        """
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
            if tool_name == "get_device_snapshot":
                result = field_iot.get_device_snapshot(
                    self.store, self.ledger, self.settings, device_ids=tool_args.get("device_ids", [])
                )
            elif tool_name == "get_metric_series":
                result = field_iot.get_metric_series(
                    self.store,
                    self.ledger,
                    self.settings,
                    device_id=tool_args.get("device_id", ""),
                    hours_back=tool_args.get("hours_back", 1),
                )
            elif tool_name == "get_freshness_report":
                result = field_iot.get_freshness_report(self.store, self.ledger, self.settings)
            elif tool_name == "get_anomaly_report":
                result = field_iot.get_anomaly_report(
                    self.store,
                    self.ledger,
                    self.settings,
                    device_id=tool_args.get("device_id", ""),
                    hours_back=tool_args.get("hours_back", 2),
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
