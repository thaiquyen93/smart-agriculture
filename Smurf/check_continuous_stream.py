import time
import json
from kafka import KafkaConsumer

print("================================================================================")
print("🔍 LISTENING TO REAL-TIME MESSAGES IN REDPANDA KAFKA (topic_raw)")
print("================================================================\n")

try:
    consumer = KafkaConsumer(
        "topic_raw",
        bootstrap_servers=["localhost:9092"],
        auto_offset_reset="latest",
        consumer_timeout_ms=10000,
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )

    msg_count = 0
    start_time = time.time()
    print("Listening for incoming messages in real-time...")
    for msg in consumer:
        msg_count += 1
        dev_id = msg.value.get("device_id") or msg.value.get("device_code")
        print(f"  ⚡ [{time.strftime('%H:%M:%S')}] Received from {dev_id}: {msg.value}")
        if msg_count >= 10:
            break

    print(f"\nTotal messages received in 10 seconds: {msg_count}")
    if msg_count == 0:
        print("⚠️ NO CONTINUOUS MESSAGES DETECTED! Stream generator/simulator is currently paused.")
except Exception as e:
    print(f"❌ Error listening to topic_raw: {e}")
