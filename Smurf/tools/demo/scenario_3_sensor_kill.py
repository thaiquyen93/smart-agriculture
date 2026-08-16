#!/usr/bin/env python3
"""
🌾 KỊCH BẢN 3: DỮ LIỆU CẢM BIẾN GIÁN ĐOẠN (PARTIAL_MODE)
===========================================================
Mục đích demo:
  - Ban đầu phát đủ 6 thiết bị để thiết lập trạng thái baseline FRESH.
  - Sau N giây (--kill-after-sec), ngắt hoàn toàn việc publish của các cảm biến
    được chọn (mặc định: PH_01 và SUN_01 đúng kịch bản tài liệu).
  - Không gửi giá trị giả; thời gian im lặng (age_seconds) tăng dần tới ngưỡng
    OFFLINE (600s).
  - Khi BTC yêu cầu: "Dữ liệu một số cảm biến vừa ngừng cập nhật. Hãy tiếp tục lập kế hoạch...",
    Agent phát hiện trạng thái thiếu hụt, kích hoạt PARTIAL_MODE (4/6 FRESH),
    tạo kế hoạch tưới thận trọng + tạo phiếu kiểm tra bảo trì SENSOR_OFFLINE.
  - Hỗ trợ tuỳ chọn hồi sinh cảm biến (--revive-after-sec) để biểu diễn phục hồi.

Cách chạy nhanh:
  python tools/demo/scenario_3_sensor_kill.py --local
  python tools/demo/scenario_3_sensor_kill.py --preset doc
  python tools/demo/scenario_3_sensor_kill.py --kill SOIL_01 --kill SUN_01
"""

import argparse
import random
import sys
from pathlib import Path

# Đảm bảo import được _shared dù chạy từ bất kỳ thư mục nào
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from _shared import (
    FarmPhysics,
    KNOWN_DEVICE_IDS,
    add_common_mqtt_args,
    banner,
    colorize,
    maybe_trigger_agent,
    run_publish_loop,
    info,
    warn,
    alert,
    success,
    BOLD,
    GREEN,
    YELLOW,
    RED,
    CYAN,
)

BTC_QUESTION = "Dữ liệu một số cảm biến vừa ngừng cập nhật. Hãy tiếp tục lập kế hoạch công việc cho đội ngoài hiện trường."


def resolve_killed_devices(args) -> list:
    """Xác định danh sách thiết bị cần ngắt tín hiệu."""
    if args.kill:
        chosen = []
        for dev in args.kill:
            dev_upper = dev.strip().upper()
            if dev_upper in KNOWN_DEVICE_IDS:
                if dev_upper not in chosen:
                    chosen.append(dev_upper)
            else:
                warn(f"Mã thiết bị không hợp lệ: '{dev}'. Bỏ qua. (Chọn từ: {', '.join(KNOWN_DEVICE_IDS)})")
        if chosen:
            return chosen

    # Xử lý theo preset
    preset = (args.preset or "doc").lower()
    if preset == "doc":
        return ["PH_01", "SUN_01"]  # Đúng kịch bản 3 trong 06-scenarios-and-acceptance.md
    elif preset == "soil":
        return ["SOIL_01"]
    elif preset == "half":
        rnd = random.Random(args.seed)
        shuffled = list(KNOWN_DEVICE_IDS)
        rnd.shuffle(shuffled)
        return shuffled[:3]
    else:
        warn(f"Preset '{preset}' không nhận diện được, chuyển về mặc định 'doc' (PH_01, SUN_01).")
        return ["PH_01", "SUN_01"]


def main():
    parser = argparse.ArgumentParser(
        description="🌾 [Kịch bản 3] Giả lập ngắt tín hiệu cảm biến -> Kích hoạt PARTIAL_MODE trong Agent",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_mqtt_args(parser)

    # Đổi mặc định duration-min thành 15 phút cho KB3
    parser.set_defaults(duration_min=15.0)

    scen_group = parser.add_argument_group("Tham số Kịch bản 3 (Ngắt cảm biến)")
    scen_group.add_argument(
        "--kill",
        action="append",
        type=str,
        help="Chỉ định thiết bị cụ thể cần ngắt (lặp lại cờ để ngắt nhiều thiết bị, vd: --kill PH_01 --kill SUN_01)",
    )
    scen_group.add_argument(
        "--preset",
        choices=["doc", "soil", "half"],
        default="doc",
        help="Preset ngắt: 'doc' (PH_01+SUN_01), 'soil' (SOIL_01), 'half' (3/6 thiết bị ngẫu nhiên)",
    )
    scen_group.add_argument("--seed", type=int, default=42, help="Seed ngẫu nhiên khi dùng --preset half")
    scen_group.add_argument(
        "--kill-after-sec",
        type=float,
        default=5.0,
        help="Thời gian duy trì baseline FRESH trước khi ngắt tín hiệu (giây)",
    )
    scen_group.add_argument(
        "--revive-after-sec",
        type=float,
        default=0.0,
        help="Thời gian phục hồi lại tín hiệu (giây, 0 = không bao giờ phục hồi)",
    )
    scen_group.add_argument(
        "--stale-threshold-sec",
        type=float,
        default=600.0,
        help="Ngưỡng im lặng để Agent xác định thiết bị OFFLINE (giây, mặc định: 600s = 10 phút)",
    )

    args = parser.parse_args()
    no_color = args.no_color

    killed_devices = resolve_killed_devices(args)
    alive_count_expected = len(KNOWN_DEVICE_IDS) - len(killed_devices)

    physics = FarmPhysics(
        soil_start=50.0,
        tank_start=85.0,
        pump_mode="auto",  # Các thiết bị còn lại hoạt động tự nhiên
    )

    kill_executed = [False]
    half_warned = [False]
    stale_reached = [False]
    revive_executed = [False]
    agent_triggered = [False]

    def filter_devices(elapsed_sec: float, all_dev_ids: list) -> set:
        """Lọc danh sách các thiết bị được phép publish tại thời điểm elapsed_sec."""
        # 1. Trước khi ngắt: tất cả đều sống
        if elapsed_sec < args.kill_after_sec:
            return set(all_dev_ids)

        # 2. Đã đến giờ phục hồi (nếu cấu hình)
        if args.revive_after_sec > 0 and elapsed_sec >= args.revive_after_sec:
            return set(all_dev_ids)

        # 3. Đang trong giai đoạn ngắt tín hiệu
        return set(dev for dev in all_dev_ids if dev not in killed_devices)

    def on_tick(round_count: int, elapsed_sec: float, farm: FarmPhysics):
        # 1. Thông báo sự kiện ngắt
        if not kill_executed[0] and elapsed_sec >= args.kill_after_sec:
            kill_executed[0] = True
            print("\n" + "=" * 75)
            msg = (
                f"🔴 [NGẮT TÍN HIỆU CẢM BIẾN] Đã ngắt kết nối: {', '.join(killed_devices)}!\n"
                f"   Các thiết bị này sẽ ngừng xuất bản dữ liệu để age_seconds tăng dần.\n"
                f"   Còn lại {alive_count_expected}/6 thiết bị đang trực tuyến."
            )
            print(colorize(msg, BOLD + RED, no_color))
            print("=" * 75 + "\n")

        # 2. Cảnh báo 50% ngưỡng OFFLINE
        kill_duration = max(0.0, elapsed_sec - args.kill_after_sec)
        half_threshold = args.stale_threshold_sec / 2.0
        if kill_executed[0] and not half_warned[0] and kill_duration >= half_threshold:
            half_warned[0] = True
            print("\n" + "-" * 75)
            msg = (
                f"⏳ [CẢNH BÁO 50% NGƯỠNG] {', '.join(killed_devices)} đã im lặng {kill_duration:.0f}s "
                f"(Đạt 50% mốc OFFLINE {args.stale_threshold_sec:.0f}s)..."
            )
            print(colorize(msg, YELLOW, no_color))
            print("-" * 75 + "\n")

        # 3. Đạt ngưỡng OFFLINE -> PARTIAL_MODE
        if kill_executed[0] and not stale_reached[0] and kill_duration >= args.stale_threshold_sec:
            stale_reached[0] = True
            print("\n" + "=" * 75)
            hint = "Đang tự động gửi câu hỏi cho Agent..." if args.auto_send else "Hãy gửi câu hỏi cho Agent thủ công."
            msg = (
                f"🚨 [NGƯỠNG OFFLINE ĐẠT ĐƯỢC - KÍCH HOẠT PARTIAL_MODE]!\n"
                f"   - {', '.join(killed_devices)} đã im lặng >= {args.stale_threshold_sec:.0f}s.\n"
                f"   - Farm State Digest trong Agent đã chuyển sang chế độ PARTIAL ({alive_count_expected}/6 FRESH).\n\n"
                f"   👉 {hint} Câu hỏi: 'Dữ liệu một số cảm biến vừa ngừng cập nhật. "
                f"Hãy tiếp tục lập kế hoạch công việc cho đội ngoài hiện trường.'"
            )
            print(colorize(msg, BOLD + RED, no_color))
            print("=" * 75 + "\n")

            maybe_trigger_agent(args, BTC_QUESTION, "KỊCH BẢN 3: CẢM BIẾN GIÁN ĐOẠN -> PARTIAL_MODE", agent_triggered)

        # 4. Phục hồi cảm biến nếu có cấu hình
        if (
            args.revive_after_sec > 0
            and not revive_executed[0]
            and elapsed_sec >= args.revive_after_sec
        ):
            revive_executed[0] = True
            print("\n" + "=" * 75)
            msg = (
                f"🟢 [PHỤC HỒI TÍN HIỆU] Đã cấp lại tín hiệu cho các cảm biến: {', '.join(killed_devices)}!\n"
                f"   Dữ liệu 6/6 thiết bị đã trở lại trạng thái FRESH."
            )
            print(colorize(msg, BOLD + GREEN, no_color))
            print("=" * 75 + "\n")

    # In thông tin kịch bản
    killed_list_str = ", ".join(killed_devices)
    subtitle = f"Ngắt: [{killed_list_str}] sau {args.kill_after_sec}s · Ngưỡng OFFLINE: {args.stale_threshold_sec}s"

    run_publish_loop(
        args=args,
        physics=physics,
        scenario_title="KỊCH BẢN 3: CẢM BIẾN GIÁN ĐOẠN -> PARTIAL_MODE",
        scenario_subtitle=subtitle,
        on_tick_fn=on_tick,
        filter_devices_fn=filter_devices,
    )


if __name__ == "__main__":
    main()
