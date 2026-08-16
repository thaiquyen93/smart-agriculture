import json
import time
from src.agents.farm_coordinator_agent import FarmCoordinatorAgent

print("================================================================================")
print("🤖 TESTING TRACK B MULTI-AGENT AI SYSTEM (5 AGENTS & 3 SCENARIOS)")
print("================================================================================\n")

coordinator = FarmCoordinatorAgent(producer=None)

# ------------------------------------------------------------------------------
# SCENARIO 1: Lập kế hoạch tưới trong ngày (Happy Path)
# ------------------------------------------------------------------------------
print("\n🌾 [KỊCH BẢN 1] Yêu cầu: 'Hãy chuẩn bị kế hoạch tưới cho khu A trong hôm nay'")
mock_states_scenario1 = {
    "SOIL_01":    {"created_at": time.time(), "payload": {"soil_moisture": 42.0, "temperature": 27.5}},
    "WEATHER_01": {"created_at": time.time(), "payload": {"temperature": 31.0, "humidity": 68.0}},
    "PUMP_01":    {"created_at": time.time(), "payload": {"flow_rate": 0.0, "power": 0.0, "status": "OFF"}},
    "PH_01":      {"created_at": time.time(), "payload": {"ph": 6.5}},
    "TANK_01":    {"created_at": time.time(), "payload": {"level": 85.0}},
    "SUN_01":     {"created_at": time.time(), "payload": {"lux": 55000.0}}
}

res1 = coordinator.process_manager_request("Hãy chuẩn bị kế hoạch tưới cho khu A", mock_states_scenario1)
print(f"\n📋 [KẾT QUẢ KỊCH BẢN 1]:\n{res1['final_summary']}")
print(f"\n🔍 [REASONING TRACE 5 AGENTS]: {len(res1['reasoning_trace'])} Bước suy luận")

# ------------------------------------------------------------------------------
# SCENARIO 2: Kiểm tra hoạt động tưới & Cảnh báo bồn nước kiệt
# ------------------------------------------------------------------------------
print("\n\n⚠️ [KỊCH BẢN 2] Yêu cầu: 'Hãy kiểm tra bồn nước và bơm tưới xem có đủ điều kiện tưới không'")
mock_states_scenario2 = {
    "SOIL_01":    {"created_at": time.time(), "payload": {"soil_moisture": 30.0, "temperature": 32.0}},
    "WEATHER_01": {"created_at": time.time(), "payload": {"temperature": 35.0, "humidity": 45.0}},
    "PUMP_01":    {"created_at": time.time(), "payload": {"flow_rate": 0.0, "power": 0.0, "status": "OFF"}},
    "PH_01":      {"created_at": time.time(), "payload": {"ph": 6.2}},
    "TANK_01":    {"created_at": time.time(), "payload": {"level": 12.0}}, # Bồn kiệt < 20%
    "SUN_01":     {"created_at": time.time(), "payload": {"lux": 70000.0}}
}

res2 = coordinator.process_manager_request("Kiểm tra điều kiện tưới", mock_states_scenario2)
print(f"\n📋 [KẾT QUẢ KỊCH BẢN 2]:\n{res2['final_summary']}")

# ------------------------------------------------------------------------------
# SCENARIO 3: Dữ liệu hiện trường bị gián đoạn (Partial Data Mode - Không bịa data)
# ------------------------------------------------------------------------------
print("\n\n📡 [KỊCH BẢN 3] Yêu cầu: 'Dữ liệu cảm biến SOIL_01 vừa bị rớt kết nối, hãy tiếp tục xử lý'")
mock_states_scenario3 = {
    "SOIL_01":    {"created_at": time.time() - 3600.0, "payload": {"soil_moisture": 40.0}}, # Stale 1h ago
    "WEATHER_01": {"created_at": time.time(), "payload": {"temperature": 29.0, "humidity": 70.0}},
    "PUMP_01":    {"created_at": time.time(), "payload": {"flow_rate": 0.0, "power": 0.0, "status": "OFF"}},
    "PH_01":      {"created_at": time.time(), "payload": {"ph": 6.6}},
    "TANK_01":    {"created_at": time.time(), "payload": {"level": 90.0}},
    "SUN_01":     {"created_at": time.time(), "payload": {"lux": 30000.0}}
}

res3 = coordinator.process_manager_request("Cảm biến ngắt kết nối", mock_states_scenario3)
print(f"\n📋 [KẾT QUẢ KỊCH BẢN 3]:\n{res3['final_summary']}")

print("\n\n🎉 BỘ 5 MULTI-AGENT AI HOÀN THÀNH 100%!")
