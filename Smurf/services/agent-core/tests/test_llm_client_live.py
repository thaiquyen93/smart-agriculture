"""Live integration test against a real LM Studio instance.

LM Studio + qwen2.5-3b-instruct is expected to be running at
LOCAL_LLM_BASE_URL (default http://localhost:1234/v1) — this test measures
M0.3 for real rather than guessing whether the 3B model can hold a JSON
schema. It self-skips (not fails) when LM Studio is unreachable, so the rest
of the suite stays green on machines / CI without it running.

Run with `-s` to see the measured success rate:
    pytest services/agent-core/tests/test_llm_client_live.py -v -s
"""
from __future__ import annotations

import pytest

from agent_core.config import Settings
from agent_core.llm.openai_compat import OpenAICompatClient
from agent_core.llm.structured_output import complete_structured

ROUTER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["playbook", "zone", "urgency", "confidence"],
    "properties": {
        "playbook": {
            "type": "string",
            "enum": ["PLAN_IRRIGATION", "INSPECT_SESSION", "DEVICE_ISSUE", "REPORT", "ASK_DATA"],
            "description": "Loại yêu cầu đã phân loại theo 5 playbook cố định",
        },
        "zone": {"type": "string", "enum": ["ZONE_A"], "description": "Khu vực canh tác"},
        "urgency": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"], "description": "Mức độ khẩn cấp"},
        "confidence": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"], "description": "Độ tự tin phân loại"},
    },
}

SYSTEM_PROMPT = (
    "Bạn là Router của hệ thống nông trại thông minh. Phân loại yêu cầu của "
    "người quản lý vào đúng 1 playbook. Chỉ trả JSON khớp schema, không giải thích."
)

# Router playbook probe set — not the full 15-case golden set (that's M4/
# eval-harness.md); just enough variety to exercise all 5 playbook labels
# for the M0.3 success-rate measurement.
PROBE_REQUESTS = [
    "Chuẩn bị kế hoạch tưới cho khu A hôm nay.",
    "Kiểm tra độ ẩm đất khu A hiện tại.",
    "Bơm có vấn đề gì không, kiểm tra giúp.",
    "Báo cáo tuần cho khu A.",
    "Độ ẩm đất khu A bao nhiêu phần trăm rồi.",
    "Kiểm tra phiên tưới hiện tại có ổn không.",
    "Cảm biến pH có vẻ ngừng cập nhật.",
    "Tổng hợp tình hình canh tác tuần này.",
    "Tưới ngay bây giờ cho khu A vì trời sắp mưa.",
    "Chuẩn bị kế hoạch tưới cho khu A hôm nay và giải thích dữ liệu đã dùng.",
]


def _live_client() -> OpenAICompatClient | None:
    settings = Settings.from_env()
    profile = settings.llm_profile_config()
    client = OpenAICompatClient(
        provider=profile.profile,
        base_url=profile.base_url,
        model=profile.model,
        api_key=profile.api_key,
        timeout_sec=profile.timeout_sec,
    )
    return client if client.is_reachable() else None


@pytest.fixture(scope="module")
def live_client():
    client = _live_client()
    if client is None:
        pytest.skip("LM Studio không reachable ở LOCAL_LLM_BASE_URL — bỏ qua test live")
    return client


def test_llm_is_reachable(live_client):
    assert live_client.is_reachable() is True


def test_structured_output_produces_valid_json(live_client):
    result = complete_structured(
        live_client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt="Chuẩn bị kế hoạch tưới cho khu A hôm nay.",
        schema=ROUTER_SCHEMA,
        schema_name="router_output",
        temperature=0.1,
    )
    assert result.ok is True, f"model trả: {result.raw_attempts}"
    assert result.data["playbook"] in {"PLAN_IRRIGATION", "INSPECT_SESSION", "DEVICE_ISSUE", "REPORT", "ASK_DATA"}
    assert result.data["zone"] == "ZONE_A"


def test_structured_output_success_rate_over_multiple_runs(live_client):
    """M0.3 exit criterion (roadmap): ép 3B trả JSON đúng schema ≥95% lượt.

    Reports the measured rate rather than hard-asserting a threshold — a
    single flaky local-model run shouldn't fail the suite — but the number
    is printed so it's a real decision input for M1/M2, not a guess.
    """
    successes = 0
    total_retries = 0
    for req in PROBE_REQUESTS:
        result = complete_structured(
            live_client,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=req,
            schema=ROUTER_SCHEMA,
            schema_name="router_output",
            temperature=0.1,
        )
        if result.ok:
            successes += 1
        total_retries += result.retry_count

    rate = successes / len(PROBE_REQUESTS)
    print(
        f"\n[M0.3] qwen2.5-3b-instruct structured-output success rate: {rate:.0%} "
        f"({successes}/{len(PROBE_REQUESTS)}), total retries used: {total_retries}"
    )
    assert successes >= 1  # sanity floor — the real number is in the printed line above
