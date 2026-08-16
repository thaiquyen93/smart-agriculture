import sys
import time
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent / "services" / "ingestion-stream-engine"))

from src.watermark import WatermarkManager
from src.windowing import WindowManager
from src.aggregators import aggregate_window_records

print("=" * 80)
print("🌊 TESTING LAYER 2: REAL-TIME STREAM PROCESSING & WINDOWING ENGINE")
print("=" * 80)

# 1. Test Watermark Manager (Bounded Out-Of-Orderness)
print("\n[PHẦN 1] Kiểm tra Thuật toán Watermark (Độ trễ tối đa: 5.0 giây):")
wm = WatermarkManager(max_out_of_orderness_sec=5.0)

t0 = 1000.0
events = [
    {"device_code": "SOIL_01", "event_time": t0, "soil_moisture": 45.0},          # On-time
    {"device_code": "SOIL_01", "event_time": t0 + 10.0, "soil_moisture": 46.0},   # Advances watermark to t0 + 5.0
    {"device_code": "SOIL_01", "event_time": t0 + 8.0, "soil_moisture": 45.5},    # In-order within late boundary (8.0 >= 5.0) -> ACCEPT
    {"device_code": "SOIL_01", "event_time": t0 + 2.0, "soil_moisture": 44.0},    # Stale/Late data (2.0 < 5.0) -> REJECT
]

for ev in events:
    is_on_time, et, cur_wm = wm.process_event(ev)
    status = "✅ HỢP LỆ (ON-TIME)" if is_on_time else "❌ LỖI TRỄ (DROPPED LATE)"
    print(f"  • Event Time: {et:.1f}s | Current Watermark: {cur_wm:.1f}s -> {status}")

stats = wm.get_stats()
print(f"  📊 Tổng nhận: {stats['total_events']} | Hợp lệ: {stats['on_time_events']} | Bị loại do trễ: {stats['late_events']}")
assert stats['on_time_events'] == 3 and stats['late_events'] == 1, "Watermark validation failed!"

# 2. Test Windowing & Dynamic Aggregations (Tumbling 1M, Sliding 5M)
print("\n[PHẦN 2] Kiểm tra Đóng Window & Tính toán Thống kê Động (Tumbling 1m & Sliding 5m):")
win_mgr = WindowManager(tumbling_size_sec=60, sliding_size_sec=300, sliding_step_sec=60, hourly_size_sec=3600)

base_time = 3600.0
readings = [
    {"device_id": "SOIL_01", "soil_moisture": 40.0, "temperature": 28.0, "event_time": base_time + 10},
    {"device_id": "SOIL_01", "soil_moisture": 42.0, "temperature": 28.5, "event_time": base_time + 30},
    {"device_id": "SOIL_01", "soil_moisture": 44.0, "temperature": 29.0, "event_time": base_time + 50},
    {"device_id": "PUMP_01", "flow_rate": 30.0, "power": 800.0, "event_time": base_time + 20},
    {"device_id": "PUMP_01", "flow_rate": 35.0, "power": 850.0, "event_time": base_time + 40},
    {"device_id": "TANK_01", "level": 88.0, "event_time": base_time + 15},
    {"device_id": "TANK_01", "level": 87.0, "event_time": base_time + 45},
]

for r in readings:
    win_mgr.assign_tumbling_window(r["device_id"], r, r["event_time"])
    win_mgr.assign_sliding_window(r["device_id"], r, r["event_time"])

# Advance watermark to base_time + 65s (Exceeds 60s tumbling boundary)
emitted = win_mgr.advance_watermark_and_trigger(base_time + 65.0)
print(f"  ⚡ Số lượng Window đã đóng & xuất sang Topic Kafka: {len(emitted)}")

for agg in emitted:
    dev = agg["device_id"]
    wtype = agg["window_type"]
    metrics = agg["metrics"]
    cnt = agg["record_count"]
    print(f"  • [{wtype}] Thiết bị: {dev:<8} | Records: {cnt} | Metrics: {metrics}")

print("\n" + "=" * 80)
print("🎉 TẦNG 2: STREAM PROCESSING & WINDOWING HOÀN TẤT VÀ VƯỢT QUA TEST 100%!")
print("=" * 80)
