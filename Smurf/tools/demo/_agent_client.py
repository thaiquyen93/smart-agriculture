"""
🌾 SMURF Demo Suite - Agent Core HTTP/SSE Client
Module dùng chung cho các CLI kịch bản demo (M5.1): tự động gửi câu hỏi BTC
tới agent-core (`POST /api/v1/agent/sessions`) và in Live Trace (agent_event
qua SSE `GET /sessions/{id}/stream`) ra terminal có màu.

Chỉ dùng thư viện chuẩn (`urllib`) — không thêm dependency mới, đúng phong
cách tối giản của `_shared.py` (chỉ paho-mqtt + python-dotenv).

Định dạng sự kiện khớp với:
  - services/agent-core/api/sessions.py (POST/GET/stream)
  - services/agent-core/agent_core/schemas/session.py (AgentEvent, AgentPhase, AgentStatus)
"""

import json
import urllib.request

from _shared import (
    BLUE,
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RED,
    WHITE,
    YELLOW,
    alert,
    banner,
    colorize,
    info,
    success,
    warn,
)

# Kết nối/tạo phiên nên nhanh; đọc SSE thì phải rộng rãi hơn nhiều vì server
# KHÔNG gửi heartbeat giữa các event (api/sessions.py chỉ yield khi có event
# mới) — một phase LLM chậm (LLM_TIMEOUT_SEC=120 cho demo, xem
# scripts/run_demo_profile.py) có thể để socket im lặng tới ~120s+overhead
# retry mà vẫn là đang xử lý bình thường, không phải treo.
CONNECT_TIMEOUT_SEC = 10.0
STREAM_READ_TIMEOUT_SEC = 200.0

PHASE_COLORS = {
    "ROUTER": CYAN,
    "COORDINATOR": CYAN,
    "WORKER": BLUE,
    "ACTION": MAGENTA,
    "TOOL": MAGENTA,
    "POLICY_GATE": YELLOW,
    "VERIFY": GREEN,
    "NARRATIVE": BOLD + GREEN,
    "DONE": BOLD + GREEN,
}

STATUS_ICON = {
    "STARTED": "⏳",
    "SUCCEEDED": "✅",
    "FAILED": "❌",
    "BLOCKED": "🚫",
    "AWAITING_APPROVAL": "⏸️",
}


class AgentClientError(Exception):
    """Lỗi kết nối/giao tiếp với agent-core (không phải lỗi logic của agent)."""


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    # OSError covers urllib.error.URLError (its base class since Py3.3) AND
    # lower-level transport failures like http.client.RemoteDisconnected
    # (server crashes/closes mid-request) that URLError alone does NOT catch
    # — those must never surface as a raw traceback during a live demo.
    except (OSError, ValueError) as e:
        raise AgentClientError(f"Không thể kết nối agent-core tại {url}: {e}") from e


def _get_json(url: str, timeout: float) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as e:
        raise AgentClientError(f"Không thể kết nối agent-core tại {url}: {e}") from e


def create_session(base_url: str, user_request: str, user_id: str = "demo-cli", timeout: float = CONNECT_TIMEOUT_SEC) -> str:
    """POST /api/v1/agent/sessions -> trả về session_id."""
    result = _post_json(
        f"{base_url.rstrip('/')}/api/v1/agent/sessions",
        {"user_request": user_request, "user_id": user_id},
        timeout=timeout,
    )
    session_id = result.get("session_id")
    if not session_id:
        raise AgentClientError(f"Phản hồi tạo phiên không có session_id: {result}")
    return session_id


def get_session(base_url: str, session_id: str, timeout: float = CONNECT_TIMEOUT_SEC) -> dict:
    """GET /api/v1/sessions/{id} -> snapshot phiên (narrative, verdict, ...)."""
    return _get_json(f"{base_url.rstrip('/')}/api/v1/sessions/{session_id}", timeout=timeout)


def _print_agent_event(event: dict, no_color: bool = False):
    phase = event.get("phase", "?")
    agent = event.get("agent", "?")
    status = event.get("status", "?")
    title = event.get("title_vi", "")
    detail = event.get("detail_vi", "")
    color = PHASE_COLORS.get(phase, WHITE)
    icon = STATUS_ICON.get(status, "•")

    print(colorize(f"\n{icon} [{phase}] {agent}", BOLD + color, no_color) + colorize(f" — {title}", color, no_color))
    if detail:
        print(colorize(f"    {detail}", DIM, no_color))

    for tc in event.get("tool_calls") or []:
        ok_icon = "✔" if tc.get("ok") else "✘"
        print(colorize(f"    🔧 {ok_icon} {tc.get('tool')}({tc.get('arguments_summary', '')}) [{tc.get('duration_ms', 0)}ms]", DIM, no_color))

    evidence = event.get("evidence_refs") or []
    if evidence:
        print(colorize(f"    📎 evidence: {', '.join(evidence)}", DIM, no_color))

    llm_call = event.get("llm_call") or {}
    if llm_call.get("used"):
        print(colorize(
            f"    🧠 LLM: {llm_call.get('provider', '?')}/{llm_call.get('model', '?')} "
            f"({llm_call.get('duration_ms', 0)}ms, {llm_call.get('prompt_tokens', 0)}+{llm_call.get('completion_tokens', 0)} tok)",
            DIM, no_color,
        ))
    else:
        print(colorize("    ⚙️  (bước tất định — không gọi LLM)", DIM, no_color))


def _print_final_summary(base_url: str, session_id: str, no_color: bool = False):
    try:
        session = get_session(base_url, session_id, timeout=CONNECT_TIMEOUT_SEC)
    except AgentClientError as e:
        warn(f"Không lấy được tổng kết phiên: {e}", no_color)
        return

    verdict = session.get("verification_verdict") or "?"
    narrative = session.get("narrative_text") or "(chưa có bản tin)"
    verdict_color = GREEN if verdict == "VERIFIED" else (YELLOW if verdict == "PARTIAL" else RED)

    banner("KẾT QUẢ PHIÊN AGENT", f"session_id={session_id} · verdict={verdict}", color=verdict_color, no_color=no_color)
    print(colorize(f"Trạng thái: {session.get('state')}", BOLD, no_color))
    print(colorize(f"Playbook:   {session.get('playbook')}", BOLD, no_color))
    print(colorize(f"Verdict:    {verdict}", BOLD + verdict_color, no_color))
    print("\n" + colorize("📰 Bản tin:", BOLD, no_color))
    print(narrative)
    print()


def run_live_trace(base_url: str, session_id: str, no_color: bool = False) -> bool:
    """Mở SSE stream cho session_id, in từng agent_event, in tổng kết khi xong.

    Trả về True nếu stream hoàn tất bình thường (session_complete), False nếu
    lỗi kết nối / timeout giữa chừng (đã in cảnh báo, không raise ra ngoài —
    không được làm chết thread telemetry đang chạy song song).
    """
    stream_url = f"{base_url.rstrip('/')}/api/v1/sessions/{session_id}/stream"
    try:
        req = urllib.request.Request(stream_url, headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=STREAM_READ_TIMEOUT_SEC) as resp:
            event_type = None
            data_line = None
            while True:
                raw = resp.readline()
                if not raw:
                    break  # server đóng kết nối
                line = raw.decode("utf-8", errors="replace").rstrip("\n")

                if line.startswith("event:"):
                    event_type = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_line = line[len("data:"):].strip()
                elif line == "":
                    # Dòng trống -> dispatch event đã tích luỹ
                    if event_type and data_line is not None:
                        try:
                            payload = json.loads(data_line)
                        except json.JSONDecodeError:
                            payload = {}
                        if event_type == "agent_event":
                            _print_agent_event(payload, no_color)
                        elif event_type == "session_complete":
                            info(f"Phiên hoàn tất (state={payload.get('state')}).", no_color)
                            _print_final_summary(base_url, session_id, no_color)
                            return True
                    event_type, data_line = None, None
            return True
    # TimeoutError trước OSError vì TimeoutError LÀ 1 loại OSError (thứ tự
    # except quyết định message cụ thể hơn được ưu tiên).
    except TimeoutError:
        alert("Hết thời gian chờ Live Trace (server im lặng quá lâu).", no_color)
        return False
    except OSError as e:
        # Bắt cả urllib.error.URLError (base class OSError từ Py3.3) lẫn lỗi
        # transport thấp hơn (vd. http.client.RemoteDisconnected khi server
        # crash/đóng kết nối giữa chừng) — không được để lộ traceback thô ra
        # terminal trong lúc demo trực tiếp.
        alert(f"Mất kết nối SSE tới agent-core giữa chừng: {e}", no_color)
        return False


def trigger_agent_and_print_trace(
    base_url: str,
    user_request: str,
    scenario_label: str = "",
    no_color: bool = False,
):
    """Hàm tiện ích gọi trong 1 thread riêng từ script kịch bản: gửi câu hỏi
    BTC tới agent-core rồi in Live Trace. Không raise — mọi lỗi kết nối được
    in ra như cảnh báo để không làm chết vòng lặp publish MQTT đang chạy
    song song ở thread chính."""
    banner(
        "📨 GỬI YÊU CẦU TỚI AGENT CORE",
        scenario_label,
        color=CYAN,
        no_color=no_color,
    )
    print(colorize(f'   "{user_request}"', BOLD, no_color))

    try:
        session_id = create_session(base_url, user_request)
    except AgentClientError as e:
        alert(f"Không gửi được yêu cầu tới agent-core ({base_url}): {e}", no_color)
        print("💡 Gợi ý: Kiểm tra agent-core đã chạy chưa (`curl {}/health`).".format(base_url))
        return

    success(f"Đã tạo phiên {session_id}. Đang chờ Live Trace...", no_color)
    ok = run_live_trace(base_url, session_id, no_color)
    if not ok:
        warn(f"Live Trace dừng giữa chừng — kiểm tra thủ công: GET {base_url}/api/v1/sessions/{session_id}", no_color)
