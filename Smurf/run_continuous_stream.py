import json
import time
import random
import math
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=["localhost:9092"],
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: str(k).encode("utf-8")
)

print("================================================================================")
print("🌾 CONTINUOUS TELEMETRY STREAM GENERATOR -> REDPANDA KAFKA (topic_raw)")
print("================================================================================")
print("📡 Generating dynamic sensor fluctuations every 2 seconds...")
print("Press Ctrl+C to stop.\n")

soil_moisture = 44.0
soil_temp = 25.0
air_temp = 31.0
air_humidity = 68.0
pump_on = False
ph_val = 6.8
tank_lvl = 85.0
sun_lux = 48000.0

count = 0
try:
    while True:
        count += 1
        now_sec = time.time()

        # Simulate natural variations
        soil_moisture = max(15.0, min(80.0, soil_moisture + random.uniform(-0.4, 0.3)))
        soil_temp = round(24.0 + random.uniform(-0.3, 0.3), 1)
        air_temp = round(30.0 + random.uniform(-0.5, 0.5), 1)
        air_humidity = round(65.0 + random.uniform(-1.0, 1.0), 1)
        ph_val = round(max(4.5, min(9.0, ph_val + random.uniform(-0.02, 0.02))), 2)
        tank_lvl = round(max(10.0, min(100.0, tank_lvl + random.uniform(-0.2, 0.1))), 1)
        sun_lux = round(max(5000.0, sun_lux + random.uniform(-500, 500)), 0)

        if soil_moisture < 35.0:
            pump_on = True
        elif soil_moisture > 60.0:
            pump_on = False

        flow_rate = round(35.5 + random.uniform(-1.5, 1.5), 1) if pump_on else 0.0
        power_w = round(850.0 + random.uniform(-20.0, 20.0), 0) if pump_on else 0.0

        devices_data = [
            {"device_id": "SOIL_01", "soil_moisture": round(soil_moisture, 1), "temperature": soil_temp, "status": "ok", "event_time": now_sec, "ingestion_time": now_sec},
            {"device_id": "WEATHER_01", "temperature": air_temp, "humidity": air_humidity, "status": "ok", "event_time": now_sec, "ingestion_time": now_sec},
            {"device_id": "PUMP_01", "status": "ON" if pump_on else "OFF", "flow_rate": flow_rate, "power": power_w, "event_time": now_sec, "ingestion_time": now_sec},
            {"device_id": "PH_01", "ph": ph_val, "status": "ok", "event_time": now_sec, "ingestion_time": now_sec},
            {"device_id": "TANK_01", "level": tank_lvl, "status": "ok", "event_time": now_sec, "ingestion_time": now_sec},
            {"device_id": "SUN_01", "lux": sun_lux, "status": "ok", "event_time": now_sec, "ingestion_time": now_sec},
        ]

        print(f"⚡ [Tick #{count}] {time.strftime('%H:%M:%S')} | Soil: {soil_moisture:.1f}% | Temp: {air_temp}°C | Pump: {'🟢 ON' if pump_on else '⚪ OFF'}")
        
        for dev in devices_data:
            producer.send("topic_raw", key=dev["device_id"], value=dev)

        producer.flush()
        time.sleep(2)

except KeyboardInterrupt:
    print("\n👋 Stopped continuous stream generator.")
