#!/usr/bin/env python3
"""
🌾 SMURF — Chọn Profile LLM Demo & Làm Nóng Model (M4.6 / M5.1)
====================================================================
Chuẩn bị `services/agent-core/.env` cho một buổi demo mượt mà:
  1. Set `LLM_PROFILE=local|gemini` (đúng 1 biến env, theo ADR-001).
  2. Nếu `gemini`: ghi `GEMINI_LLM_API_KEY` (từ cờ --gemini-api-key hoặc
     biến môi trường GOOGLE_API_KEY).
  3. Nâng `LLM_TIMEOUT_SEC` lên tối thiểu 120s cho buổi demo.
  4. "Làm nóng" (prewarm) provider bằng 1 chat completion nhỏ gọi thẳng
     LLM base_url — với LM Studio việc này buộc model phải load vào
     VRAM trước khi BGK hỏi câu đầu tiên; với cả hai provider, phần
     system-prompt lặp lại giữa các lượt gọi sau đó tận dụng được cache
     có sẵn của chính provider (KV-cache phía LM Studio / context caching
     phía Gemini) — script này KHÔNG (và không được phép, xem phạm vi
     phiên làm việc) sửa code trong agent_core/llm/.

CHỈ chỉnh sửa `services/agent-core/.env` — không đụng code nguồn agent-core.

Cách dùng:
    python scripts/run_demo_profile.py --profile local
    python scripts/run_demo_profile.py --profile gemini --gemini-api-key AIza...
    python scripts/run_demo_profile.py --profile gemini            # đọc GOOGLE_API_KEY từ env
    python scripts/run_demo_profile.py --profile local --skip-prewarm
"""

import argparse
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"


def _c(text: str, code: str, no_color: bool) -> str:
    if no_color or not sys.stdout.isatty():
        return str(text)
    return f"{code}{text}{RESET}"


def info(msg, no_color=False):
    print(_c(f"ℹ️  {msg}", CYAN, no_color))


def ok(msg, no_color=False):
    print(_c(f"✅ {msg}", GREEN, no_color))


def warn(msg, no_color=False):
    print(_c(f"⚠️  {msg}", YELLOW, no_color))


def fail(msg, no_color=False):
    print(_c(f"❌ {msg}", BOLD + RED, no_color))


TARGET_TIMEOUT_SEC = 120


def _read_env_lines(path: Path) -> list:
    return path.read_text(encoding="utf-8").splitlines(keepends=False)


def _get_env_value(lines: list, key: str):
    prefix = f"{key}="
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].split("#", 1)[0].strip()
    return None


def _set_env_value(lines: list, key: str, value: str) -> list:
    """Thay giá trị dòng `KEY=...` đầu tiên (bỏ qua dòng comment), hoặc thêm
    dòng mới cuối file nếu chưa có key này."""
    prefix = f"{key}="
    out = []
    replaced = False
    for line in lines:
        if not replaced and line.strip().startswith(prefix):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    return out


def prewarm(base_url: str, model: str, api_key: str, timeout_sec: float, no_color: bool) -> bool:
    """Gửi 1 chat completion nhỏ thẳng tới LLM base_url (không qua agent-core)
    để buộc model load / kết nối được thiết lập trước khi BGK hỏi câu đầu."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Bạn là trợ lý nông trại SMURF. Trả lời ngắn gọn."},
            {"role": "user", "content": "Sẵn sàng chưa? Trả lời đúng 1 từ: OK"},
        ],
        "max_tokens": 8,
        "temperature": 0.1,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key or 'not-needed'}",
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            resp.read()
        duration_ms = int((time.monotonic() - started) * 1000)
        ok(f"Prewarm thành công ({model} @ {base_url}) trong {duration_ms}ms.", no_color)
        return True
    except OSError as e:
        # OSError bắt cả urllib.error.URLError (base class từ Py3.3) lẫn lỗi
        # transport thấp hơn (server đóng kết nối giữa chừng khi cold-start).
        duration_ms = int((time.monotonic() - started) * 1000)
        warn(f"Prewarm thất bại sau {duration_ms}ms: {e}", no_color)
        warn("(Bình thường nếu LM Studio/agent-core chưa khởi động — xem 04-integration-guide.md §8)", no_color)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="🌾 Chọn LLM_PROFILE demo (local|gemini) và làm nóng model trước khi BGK hỏi.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--profile", choices=["local", "gemini"], required=True, help="Provider LLM dùng cho buổi demo")
    parser.add_argument("--gemini-api-key", type=str, default=None, help="API key Gemini (nếu không truyền, đọc GOOGLE_API_KEY từ env, rồi tới giá trị đã có sẵn trong .env)")
    parser.add_argument("--skip-prewarm", action="store_true", help="Không gửi request làm nóng model")
    parser.add_argument("--no-color", action="store_true", help="Tắt màu sắc terminal")
    args = parser.parse_args()
    no_color = args.no_color

    repo_root = Path(__file__).resolve().parent.parent
    agent_core_dir = repo_root / "services" / "agent-core"
    env_path = agent_core_dir / ".env"
    example_path = agent_core_dir / ".env.example"

    if not env_path.exists():
        if not example_path.exists():
            fail(f"Không tìm thấy {example_path} để tạo .env mẫu.", no_color)
            sys.exit(1)
        shutil.copyfile(example_path, env_path)
        info(f"Đã tạo {env_path} từ .env.example.", no_color)

    lines = _read_env_lines(env_path)

    gemini_api_key = None
    if args.profile == "gemini":
        gemini_api_key = (
            args.gemini_api_key
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_LLM_API_KEY")
            or _get_env_value(lines, "GEMINI_LLM_API_KEY")
        )
        if not gemini_api_key:
            fail(
                "Thiếu Gemini API key. Truyền qua --gemini-api-key, hoặc set biến môi trường "
                "GOOGLE_API_KEY, hoặc điền sẵn GEMINI_LLM_API_KEY trong services/agent-core/.env.",
                no_color,
            )
            sys.exit(1)  # thoát TRƯỚC khi ghi file — không để .env ở trạng thái dở dang
        lines = _set_env_value(lines, "GEMINI_LLM_API_KEY", gemini_api_key)

    lines = _set_env_value(lines, "LLM_PROFILE", args.profile)

    current_timeout = _get_env_value(lines, "LLM_TIMEOUT_SEC")
    try:
        current_timeout_val = float(current_timeout) if current_timeout else 0.0
    except ValueError:
        current_timeout_val = 0.0
    if current_timeout_val < TARGET_TIMEOUT_SEC:
        lines = _set_env_value(lines, "LLM_TIMEOUT_SEC", str(TARGET_TIMEOUT_SEC))
        info(f"Nâng LLM_TIMEOUT_SEC: {current_timeout or '(chưa có)'} -> {TARGET_TIMEOUT_SEC}", no_color)

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok(f"Đã cập nhật {env_path} (LLM_PROFILE={args.profile}).", no_color)

    # Đọc lại các giá trị cần cho prewarm từ file vừa ghi
    if args.profile == "gemini":
        base_url = _get_env_value(lines, "GEMINI_LLM_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = _get_env_value(lines, "GEMINI_LLM_MODEL") or "gemini-2.5-flash"
        api_key = gemini_api_key
    else:
        base_url = _get_env_value(lines, "LOCAL_LLM_BASE_URL") or "http://localhost:1234/v1"
        model = _get_env_value(lines, "LOCAL_LLM_MODEL") or "qwen2.5-3b-instruct"
        api_key = _get_env_value(lines, "LOCAL_LLM_API_KEY") or "lm-studio"

    print()
    print(_c(f"{'=' * 60}", CYAN, no_color))
    print(_c(f"  Profile:  {args.profile}", BOLD, no_color))
    print(_c(f"  Model:    {model}", BOLD, no_color))
    print(_c(f"  Base URL: {base_url}", BOLD, no_color))
    print(_c(f"  Timeout:  {TARGET_TIMEOUT_SEC}s", BOLD, no_color))
    print(_c(f"{'=' * 60}", CYAN, no_color))
    print()

    if args.skip_prewarm:
        info("Bỏ qua bước prewarm (--skip-prewarm).", no_color)
    else:
        info("Đang gửi request làm nóng model...", no_color)
        prewarm(base_url, model, api_key, timeout_sec=TARGET_TIMEOUT_SEC, no_color=no_color)

    print()
    ok("Sẵn sàng. Tiếp theo: chạy script kịch bản demo, vd. `python tools/demo/scenario_1_normal.py --local`.", no_color)


if __name__ == "__main__":
    main()
