"""Field IoT Agent — wrapper around 4 M1 Field IoT tools.

Follows docs/agent-core/02-agents-and-tools.md §B.2.
Role: "Gác cổng độ mới dữ liệu" — guards data freshness.

Rule 1 (CLAUDE.md — "LLM đề xuất, code định đoạt"): code decides which
tools to call (deterministic, always the same fixed set for this playbook),
executes them directly, then makes exactly ONE LLM call to turn the tool
output into structured findings. The local 3B model is never asked to emit
tool_calls — `complete_structured()`/`OpenAICompatClient` don't support
that, and `local_use_native_tool_calling=False` says so explicitly.
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
from agent_core.tools import field_iot

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

Nhiệm vụ: Đọc kết quả 3 tool đã được code gọi sẵn (get_freshness_report, get_device_snapshot,
get_anomaly_report) và tổng hợp thành findings có cấu trúc.

Luật quan trọng:
- Luôn kiểm tra độ tươi dữ liệu TRƯỚC KHI kết luận
- Nếu dữ liệu STALE (>5 phút) hoặc OFFLINE → cảnh báo ngay, đặt freshness_ok=False
- Không đưa ra con số cụ thể trong summary_vi — chỉ tham chiếu evidence_refs đã có trong tool result
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

    def __init__(self, store: FarmStateStore, ledger: EvidenceLedger, settings: Settings, client: LLMClient):
        self.store = store
        self.ledger = ledger
        self.settings = settings
        self.client = client

    def execute(self, session_context: dict) -> dict:
        """Execute Field IoT Agent.

        Returns: {findings, recommendation, ready_for_next_stage, llm_call_metadata, duration_ms}
        """
        start_time = time.time()

        user_request = session_context.get("user_request", "")
        zone = session_context.get("zone", ZONE)

        # Code decides which tools to call — always the same fixed set for
        # PLAN_IRRIGATION (bounded, ≤4 tools per agent per CLAUDE.md rule 6).
        tool_results = self._run_tools(zone)
        tool_results_text = "\n\n".join(f"Tool: {tr['tool']}\nResult:\n{tr['result']}" for tr in tool_results)

        user_prompt = f"""Yêu cầu người dùng: {user_request}
Khu vực: {zone}

Kết quả tool đã chạy:
{tool_results_text}

Tổng hợp thành findings. Trả về JSON theo schema."""

        try:
            result = complete_structured(
                self.client,
                system_prompt=FIELD_IOT_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=FIELD_IOT_RESULT_SCHEMA,
                schema_name="FieldIoTResult",
                temperature=self.settings.llm_temperature_decision,
            )

            if not result.ok:
                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "findings": [],
                    "recommendation": f"Field IoT Agent LLM failed: {result.message}",
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
            logger.error("FieldIoTAgent execute failed: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "findings": [],
                "recommendation": f"Exception: {exc}",
                "ready_for_next_stage": False,
                "llm_call_metadata": LLMCallMetadata(used=False),
                "duration_ms": duration_ms,
            }

    def _run_tools(self, zone: str) -> list[dict]:
        """Deterministically call the fixed Field IoT tool set.

        Returns: [{tool, result}] — `result` is the markdown table/summary
        the tools already produce for LLM consumption.
        """
        results = []

        freshness = field_iot.get_freshness_report(self.store, self.ledger, self.settings)
        snapshot = field_iot.get_device_snapshot(self.store, self.ledger, self.settings, device_ids=[])
        anomalies = field_iot.get_anomaly_report(self.store, self.ledger, self.settings, zone=zone, lookback_minutes=60)

        for tool_name, tool_result in [
            ("get_freshness_report", freshness),
            ("get_device_snapshot", snapshot),
            ("get_anomaly_report", anomalies),
        ]:
            if tool_result.get("ok"):
                result_text = tool_result.get("markdown", json.dumps(tool_result, indent=2))
            else:
                result_text = f"ERROR: {tool_result.get('message', tool_result.get('error', 'Unknown error'))}"
            results.append({"tool": tool_name, "result": result_text})

        return results
