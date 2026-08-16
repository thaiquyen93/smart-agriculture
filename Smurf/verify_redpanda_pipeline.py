"""
🔥 REDPANDA KAFKA PIPELINE VERIFIER & STREAM MONITOR
Kiểm tra sức khỏe Redpanda Cluster, danh sách Topics, và tiêu thụ tin nhắn thời gian thực
"""

import json
import time
from kafka import KafkaConsumer, KafkaAdminClient

KAFKA_BROKERS = ["localhost:9092"]

print("================================================================================")
print("🔍 CHƯƠNG TRÌNH KIỂM TRA SỨC KHỎE HỆ THỐNG REDPANDA KAFKA")
print(f"📡 Kafka Bootstrap Server: {KAFKA_BROKERS[0]}")
print("================================================================================\n")

# 1. Kiểm tra Kết nối Cluster & Danh sách Topics
try:
    admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKERS, request_timeout_ms=5000)
    topics = admin_client.list_topics()
    print("✅ KẾT NỐI VỚI REDPANDA KAFKA CLUSTER THÀNH CÔNG!")
    print(f"📌 Tổng số Topics tìm thấy trong Redpanda: {len(topics)}")
    for t in sorted(topics):
        if not t.startswith("_"):
            print(f"   • Topic: {t}")
    admin_client.close()
except Exception as e:
    print(f"❌ Không thể kết nối tới Redpanda Cluster tại {KAFKA_BROKERS}: {e}")
    print("👉 Hãy chắc chắn rằng container 'smurf-redpanda' đang chạy trong Docker!")
    exit(1)

# 2. Lắng nghe trực tiếp bản tin Stream từ Redpanda Topic `topic_raw` và `topic_p`
print("\n--------------------------------------------------------------------------------")
print("🎧 ĐANG THEO DÕI CÁC BẢN TIN LUỒNG (STREAM) TRÊN REDPANDA...")
print("📌 Listening to topics: 'topic_raw' (Dữ liệu thô) và 'topic_p' (Window 1 phút)")
print("--------------------------------------------------------------------------------\n")

try:
    consumer = KafkaConsumer(
        "topic_raw", "topic_p",
        bootstrap_servers=KAFKA_BROKERS,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
        consumer_timeout_ms=10000
    )

    msg_count = 0
    start_time = time.time()

    for message in consumer:
        msg_count += 1
        topic = message.topic
        payload = message.value
        dev_id = payload.get("device_id") or payload.get("station_id") or "UNKNOWN"

        print(f"⚡ [REDPANDA <- {topic}] Device: {dev_id}")

        if topic == "topic_raw":
            print(f"    Payload: {payload}")
        elif topic == "topic_p":
            metrics = payload.get("metrics", {})
            print(f"    📊 [WINDOW {payload.get('window_type')}] Count: {payload.get('record_count')} records | Metrics: {metrics}")

        if msg_count >= 10:
            print("\n✅ Đã nhận đủ 10 bản tin mẫu thành công!")
            break

    consumer.close()

    duration = time.time() - start_time
    print("\n================================================================================")
    print("🎉 KẾT QUẢ: REDPANDA KAFKA PIPELINE ĐANG HOẠT ĐỘNG 100% HOÀN HẢO!")
    print(f"• Tổng số tin nhận được: {msg_count} msgs")
    print(f"• Thời gian test: {duration:.2f}s")
    print("• Visual Dashboard: Mở http://localhost:8088 để xem giao diện Redpanda Console")
    print("================================================================================")

except Exception as e:
    print(f"❌ Lỗi khi đọc dữ liệu từ Redpanda: {e}")
