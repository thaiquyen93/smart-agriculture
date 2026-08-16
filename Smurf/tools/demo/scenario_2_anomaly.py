#!/usr/bin/env python3
"""
🌾 KỊCH BẢN 2: CHẨN ĐOÁN BẤT THƯỜNG BƠM / ỐNG TƯỚI
=====================================================
Mục đích demo:
  - Máy bơm PUMP_01 chạy ổn định (~12 L/min, ~750W, status ON).
  - Bồn nước TANK_01 giảm dần (nước thực sự được bơm đi).
  - Cảm biến độ ẩm SOIL_01 bị ghim quanh mức ~32%, KHÔNG TĂNG dù bơm đã chạy >10 phút.
  - Khi BTC yêu cầu: "Hãy kiểm tra phiên tưới hiện tại...", Agent phát hiện
    sự bất thường giữa lưu lượng bơm và độ ẩm đất (cross-device anomaly),
    đưa ra 3 giả thuyết (vỡ ống, tắc đầu tưới, hỏng cảm biến) và tạo phiếu kiểm tra.

Cách chạy nhanh:
  python tools/demo/scenario_2_anomaly.py --local
  python tools/demo/scenario_2_anomaly.py --duration-min 15
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
    run_publish_loop,
    warn,
    alert,
    BOLD,
    YELLOW,
    RED,
    CYAN,
)


def main():
    parser = argparse.ArgumentParser(
        description="🌾 [Kịch bản 2] Giả lập bất thường: Bơm đang tưới nhưng đất không ẩm lên (vỡ ống / tắc / hỏng cảm biến)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    add_common_mqtt_args(parser)

    # Đổi mặc định duration-min thành 15 phút cho KB2
    parser.set_defaults(duration_min=15.0)

    scen_group = parser.add_argument_group("Tham số Kịch bản 2 (Bất thường tưới)")
    scen_group.add_argument("--frozen-moisture", type=float, default=32.0, help="Độ ẩm đất bị ghim cố định (%%)")
    scen_group.add_argument("--tank-level", type=float, default=80.0, help="Mức nước bồn ban đầu (%%)")

    args = parser.parse_args()
    no_color = args.no_color

    physics = FarmPhysics(
        soil_start=args.frozen_moisture,
        tank_start=args.tank_level,
        pump_mode="forced_on",  # Ép bơm chạy liên tục
        soil_freeze=args.frozen_moisture,  # Đất không tăng ẩm
    )

    checkpoint_5m = [False]
    checkpoint_10m = [False]

    def on_tick(round_count, elapsed, farm: FarmPhysics):
        if not checkpoint_5m[0] and elapsed >= 300:
            checkpoint_5m[0] = True
            print("\n" + "-" * 75)
            msg = (
                f"⏱️  [5 PHÚT TRÔI QUA] PUMP_01 đang chạy ({farm.pump_flow_rate:.1f} L/min, {farm.pump_power:.0f}W).\n"
                f"   Độ ẩm đất SOIL_01 vẫn đứng yên ở {farm.soil_moisture:.1f}% (Bất thường đang hình thành...)"
            )
            print(colorize(msg, YELLOW, no_color))
            print("-" * 75 + "\n")

        if not checkpoint_10m[0] and elapsed >= 600:
            checkpoint_10m[0] = True
            print("\n" + "=" * 75)
            msg = (
                f"🚨 [ĐỦ ĐIỀU KIỆN DEMO KỊCH BẢN 2] Đã trôi qua 10 phút tưới liên tục!\n"
                f"   - PUMP_01: Bơm chạy ổn định ({farm.pump_flow_rate:.1f} L/min, {farm.pump_power:.0f}W, status: ON)\n"
                f"   - TANK_01: Mức nước đã giảm xuống {farm.tank_level:.1f}%\n"
                f"   - SOIL_01: Độ ẩm đất bất biến tại {farm.soil_moisture:.1f}% (Không thấm nước)\n\n"
                f"   👉 Hãy gửi câu hỏi cho Agent: 'Hãy kiểm tra phiên tưới hiện tại và chuẩn bị công việc cần thực hiện nếu kết quả không như mong đợi.'"
            )
            print(colorize(msg, BOLD + RED, no_color))
            print("=" * 75 + "\n")

    run_publish_loop(
        args=args,
        physics=physics,
        scenario_title="KỊCH BẢN 2: CHẨN ĐOÁN BẤT THƯỜNG BƠM / ỐNG TƯỚI",
        scenario_subtitle="PUMP_01 ON · TANK_01 Giảm · SOIL_01 Ghim cứng tại 32% (Lỗi vỡ ống/cảm biến)",
        on_tick_fn=on_tick,
    )


if __name__ == "__main__":
    main()
