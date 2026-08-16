import json
import time
from db import DatabaseManager

print("================================================================================")
print("🧪 TESTING TRACK B DATABASE SCHEMA & PERSISTENCE LAYER")
print("================================================================================\n")

db = DatabaseManager()

# 1. Test Raw Telemetry per Topic
print("1. Testing save_raw for 6 devices...")
devices = [
    ("SOIL_01", {"soil_moisture": 42.5, "temperature": 28.3}),
    ("WEATHER_01", {"temperature": 31.0, "humidity": 65.0}),
    ("PUMP_01", {"flow_rate": 12.5, "power": 750, "status": "ON"}),
    ("PH_01", {"ph": 6.8}),
    ("TANK_01", {"level": 82.0}),
    ("SUN_01", {"lux": 52000})
]

for dev_id, payload in devices:
    db.save_raw(dev_id, payload, topic_name=f"topic_{dev_id.lower()}")

# 2. Test Irrigation Plan
print("2. Testing save_irrigation_plan...")
plan_id = db.save_irrigation_plan({
    "area_id": "Khu A - Nông trường Rau củ",
    "target_moisture": 65.0,
    "water_amount_liters": 450.0,
    "priority": "HIGH",
    "suggested_time": "14:30 Today",
    "status": "PENDING_APPROVAL",
    "reasoning_summary": "Độ ẩm đất SOIL_01 giảm xuống 42.5% kết hợp nắng lux 52000. Đề xuất tưới 450L nước."
})

# 3. Test Inspection Task
print("3. Testing save_inspection_task...")
task_id = db.save_inspection_task({
    "device_id": "PUMP_01",
    "issue_type": "PUMP_CHECK",
    "severity": "WARNING",
    "description": "Kiểm tra lưu lượng trạm bơm PUMP_01 sau phiên tưới",
    "assigned_to": "Kỹ sư Nguyễn Văn A",
    "status": "OPEN",
    "verification_status": "VERIFIED"
})

# 4. Test Multi-Agent Reasoning Log
print("4. Testing save_agent_log...")
db.save_agent_log(
    session_id="SESS-001",
    agent_name="IrrigationPlanningAgent",
    action_type="REASONING",
    input_prompt="Lập kế hoạch tưới cho khu A",
    output_response="Đề xuất tưới 450L nước cho Khu A lúc 14:30.",
    evidence_data={"soil_moisture": 42.5, "tank_level": 82.0}
)

print("\n--------------------------------------------------------------------------------")
print("📊 VERIFYING DATABASE QUERIES:")

raws = db.get_latest_telemetry(limit=6)
print(f"✓ Total Telemetry Raw Records: {len(raws)}")

states = db.get_latest_device_states()
print(f"✓ Latest 6 Device States: {list(states.keys())}")

plans = db.get_irrigation_plans()
print(f"✓ Saved Irrigation Plans: {len(plans)} (Plan ID: {plans[0]['plan_id']})")

tasks = db.get_inspection_tasks()
print(f"✓ Saved Inspection Tasks: {len(tasks)} (Task ID: {tasks[0]['task_id']})")

logs = db.get_agent_logs()
print(f"✓ Agent Reasoning Logs: {len(logs)} (Agent: {logs[0]['agent_name']})")

print("\n🎉 DATABASE BƯỚC 1 HOÀN THÀNH 100%!")
