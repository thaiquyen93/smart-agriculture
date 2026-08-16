#!/usr/bin/env python3
"""
🌾 KỊCH BẢN 1: LẬP KẾ HOẠCH TƯỚI TỐI ƯU TRONG NGÀY
=====================================================
Mục đích demo:
  - Đất khô dần đều từ mức vừa phải (~55%) xuống mức cần tưới (~28%).
  - Bồn nước đầy (~85%), bơm chưa chạy (forced_off), thời tiết nắng ấm.
  - Toàn bộ 6/6 thiết bị liên tục phát dữ liệu FRESH.
  - Khi BTC yêu cầu: "Hãy chuẩn bị kế hoạch tưới cho khu A...", Agent sẽ nhận
    đủ bằng chứng FRESH và điều phối 6 sub-agents lập kế hoạch tối ưu.

Cách chạy nhanh:
  python tools/demo/scenario_1_normal.py --local
  python tools/demo/scenario_1_normal.py              # Dùng broker BTC trong .env
"""

import argparse
import sys
from pathlib import Path

# Đảm bảo import được _shared dù chạy từ bất kỳ thư mục nào
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from _shared import (
    FarmPhysics,
    add_common_mqtt_args,
    banner,
    colorize,
    maybe_trigger_agent,
    run_publish_loop,
    success,
    BOLD,
    GREEN,
    YELLOW,
    CYAN,
)

BTC_QUESTION = "Hãy chuẩn bị kế hoạch tưới cho khu A trong hôm nay và giải thích dữ liệu đã sử dụng."


def main():
    parser = argparse.ArgumentParser(
        description="🌾 [Kịch bản 1] Giả lập dữ liệu cho kịch bản Lập kế hoạch tưới tối ưu (6/6 thiết bị FRESH, đất khô dần)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_mqtt_args(parser)

    scen_group = parser.add_argument_group("Tham số Kịch bản 1 (Tưới tối ưu)")
    scen_group.add_argument("--start-moisture", type=float, default=55.0, help="Độ ẩm đất ban đầu (%%)")
    scen_group.add_argument("--target-moisture", type=float, default=28.0, help="Độ ẩm đất mục tiêu để báo sẵn sàng demo (%%)")
    scen_group.add_argument("--tank-level", type=float, default=85.0, help="Mức nước bồn chính (%%)")
    scen_group.add_argument("--dry-multiplier", type=float, default=4.0, help="Hệ số tăng tốc độ bốc hơi đất (giúp đạt ngưỡng tưới nhanh trong 3-5 phút)")

    args = parser.parse_args()
    no_color = args.no_color

    physics = FarmPhysics(
        soil_start=args.start_moisture,
        tank_start=args.tank_level,
        pump_mode="forced_off",  # Bơm tắt để chờ Agent quyết định
        dry_multiplier=args.dry_multiplier,
    )

    target_reached = [False]
    agent_triggered = [False]

    def on_tick(round_count, elapsed, farm: FarmPhysics):
        if not target_reached[0] and farm.soil_moisture <= args.target_moisture:
            target_reached[0] = True
            print("\n" + "=" * 75)
            hint = "Đang tự động gửi câu hỏi cho Agent..." if args.auto_send else "Hãy gửi câu hỏi cho Agent thủ công."
            msg = (
                f"🎯 [SẴN SÀNG DEMO KỊCH BẢN 1] Độ ẩm đất đã đạt {farm.soil_moisture:.1f}% (<= {args.target_moisture:.1f}%).\n"
                f"   6/6 thiết bị đều FRESH, bồn nước {farm.tank_level:.1f}% dồi dào.\n"
                f"   👉 {hint} Câu hỏi: 'Hãy chuẩn bị kế hoạch tưới cho khu A trong hôm nay...'"
            )
            print(colorize(msg, BOLD + GREEN, no_color))
            print("=" * 75 + "\n")

            maybe_trigger_agent(args, BTC_QUESTION, "KỊCH BẢN 1: LẬP KẾ HOẠCH TƯỚI TỐI ƯU", agent_triggered)

    run_publish_loop(
        args=args,
        physics=physics,
        scenario_title="KỊCH BẢN 1: LẬP KẾ HOẠCH TƯỚI TỐI ƯU",
        scenario_subtitle="6/6 thiết bị FRESH · Đất khô dần · Bồn nước đầy · Bơm chờ lệnh",
        on_tick_fn=on_tick,
    )


if __name__ == "__main__":
    main()
