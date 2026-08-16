import json
import time
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: str(k).encode("utf-8")
)

test_devices = [
    {"device_id": "SOIL_01", "soil_moisture": 45.2, "temperature": 26.5, "status": "ok"},
    {"device_id": "WEATHER_01", "temperature": 32.1, "humidity": 65.0, "status": "ok"},
    {"device_id": "PUMP_01", "status": "ON", "flow_rate": 35.5, "power": 850.0},
    {"device_id": "PH_01", "ph": 6.8, "status": "ok"},
    {"device_id": "TANK_01", "level": 78.5, "status": "ok"},
    {"device_id": "SUN_01", "lux": 52400.0, "status": "ok"},
]

print("================================================================================")
print("🚀 PUSHING TEST TELEMETRY DATA TO REDPANDA KAFKA (topic_raw)")
print("================================================================================\n")

for dev in test_devices:
    dev["event_time"] = time.time()
    dev["ingestion_time"] = time.time()
    producer.send("topic_raw", key=dev["device_id"], value=dev)
    print(f"✅ Sent {dev['device_id']}: {dev}")

producer.flush()
print("\n🎉 Đã đẩy 6 bản tin thô vào topic_raw thành công! Kiểm tra giao diện web http://localhost:3002 ngay!")
