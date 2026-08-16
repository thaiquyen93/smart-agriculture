import urllib.request
import json
import time
from kafka import KafkaConsumer

print("================================================================================")
print("🔍 DEBUGGING DATA PIPELINE FROM REDPANDA (topic_raw) TO NESTJS BACKEND")
print("================================================================\n")

# 1. Check NestJS API
try:
    req = urllib.request.urlopen("http://localhost:8000/api/v1/telemetry/latest", timeout=3)
    data = json.loads(req.read().decode())
    print(f"✅ NestJS Backend (http://localhost:8000) returned {len(data)} items:")
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"❌ NestJS Backend Error: {e}")

# 2. Check Redpanda Kafka topic_raw
print("\n🔍 Listening to Redpanda Kafka 'topic_raw' for 5 seconds...")
try:
    consumer = KafkaConsumer(
        "topic_raw",
        bootstrap_servers=["localhost:9092"],
        auto_offset_reset="latest",
        consumer_timeout_ms=5000,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    count = 0
    for msg in consumer:
        count += 1
        print(f"  📩 [topic_raw Msg {count}] Device: {msg.value.get('device_id')} | Payload: {msg.value}")
        if count >= 6:
            break
    if count == 0:
        print("  ⚠️ No new messages published to 'topic_raw' in the last 5 seconds.")
except Exception as e:
    print(f"❌ Redpanda Error: {e}")
