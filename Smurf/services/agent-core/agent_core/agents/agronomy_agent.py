"""Agronomy Agent — crop science and water demand estimation.

Follows docs/agent-core/02-agents-and-tools.md §B.3.
Role: "Phán đoán nông học" — agronomic judgment (no raw calculation).

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
from agent_core.tools import agronomy

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

Nhiệm vụ: Đọc kết quả 3 tool đã được code gọi sẵn (estimate_et0, estimate_water_demand,
forecast_soil_moisture) và phán đoán nông học dựa trên đó.

Luật quan trọng:
- Không tự tính toán số liệu — chỉ diễn giải kết quả tool đã có
- Xem xét đánh đổi: tưới ngay vs hoãn (vì nhiệt độ, ánh sáng cao điểm)
- Không đưa ra con số cụ thể trong summary_vi — chỉ tham chiếu evidence_refs đã có trong tool result
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


class AgronomyAgent:
    """Agronomy Agent — crop science and water demand estimation."""

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings, client: LLMClient):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.client = client

    def execute(self, session_context: dict) -> dict:
        """Execute Agronomy Agent.

        Returns: {findings, recommendation, ready_for_next_stage, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        zone = session_context.get("zone", ZONE)
        crop_type = session_context.get("crop_type", "cam")  # Default: orange
        horizon_hours = session_context.get("horizon_hours", 24)

        tool_results = self._run_tools(zone, crop_type, horizon_hours)
        tool_results_text = "\n\n".join(f"Tool: {tr['tool']}\nResult:\n{tr['result']}" for tr in tool_results)

        user_prompt = f"""Yêu cầu người dùng: {user_request}
Khu vực: {zone}
Loại cây trồng: {crop_type}
Khung giờ dự kiến: {horizon_hours}h tới

Kết quả tool đã chạy:
{tool_results_text}

Xem xét timing: nên tưới ngay hay hoãn (vì nhiệt độ, ánh sáng). Trả về JSON theo schema."""

        try:
            result = complete_structured(
                self.client,
                system_prompt=AGRONOMY_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=AGRONOMY_RESULT_SCHEMA,
                schema_name="AgronomyResult",
                temperature=self.settings.llm_temperature_decision,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "findings": [],
                    "recommendation": f"Agronomy Agent LLM failed: {result.message}",
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
            logger.error("AgronomyAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": [],
                "recommendation": f"Exception: {exc}",
                "ready_for_next_stage": False,
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _run_tools(self, zone: str, crop_type: str, horizon_hours: int) -> list[dict]:
        """Deterministically call the fixed Agronomy tool set."""
        results = []

        et0 = agronomy.estimate_et0(self.store, self.ledger, self.settings, zone=zone, date_iso=to_iso(time.time()))
        water_demand = agronomy.estimate_water_demand(
            self.store, self.ledger, self.settings, zone=zone, crop_type=crop_type, horizon_hours=horizon_hours
        )
        forecast = agronomy.forecast_soil_moisture(
            self.store, self.ledger, self.settings, zone=zone, horizon_hours=horizon_hours
        )

        for tool_name, tool_result in [
            ("estimate_et0", et0),
            ("estimate_water_demand", water_demand),
            ("forecast_soil_moisture", forecast),
        ]:
            if tool_result.get("ok"):
                result_text = tool_result.get("markdown", json.dumps(tool_result, indent=2))
            else:
                result_text = f"ERROR: {tool_result.get('message', 'Unknown error')}"
            results.append({"tool": tool_name, "result": result_text})

        return results
