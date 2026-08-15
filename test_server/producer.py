import json
import time
from kafka import KafkaProducer

def run_test_producer():
    print("⏳ Đang kết nối tới Redpanda (localhost:9092)...")
    producer = KafkaProducer(
        bootstrap_servers=["localhost:9092"],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None
    )

    topic_name = "test-topic"
    print(f"🚀 Bắt đầu bắn 10 bản tin vào topic '{topic_name}'...")

    for i in range(1, 11):
        message = {
            "id": i,
            "sensor": "DHT22_Soil",
            "moisture_pct": 65.5 + i,
            "temp_c": 28.0 + (i * 0.2),
            "timestamp": time.time()
        }
        
        # Bắn message vào topic
        producer.send(topic_name, key=f"sensor_{i}", value=message)
        print(f"  -> Đã gửi bản tin {i}: {message}")
        time.sleep(0.3)

    # Ép Redpanda ghi xuống đĩa ngay lập tức
    producer.flush()
    producer.close()
    print("\n✅ Đã gửi xong 10 bản tin!")
    print("👉 Bây giờ bạn hãy mở thư mục: test_server/storage/kafka/ để xem các file .log được sinh ra!")

if __name__ == "__main__":
    run_test_producer()
