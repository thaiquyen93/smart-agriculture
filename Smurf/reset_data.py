"""
🧹 CLEAN & RESET ALL TEST DATA FROM REDPANDA KAFKA & SQLITE DATABASE
Clears test/simulator messages so only clean official BTC data is processed.
"""

import os
import time
from pathlib import Path
from kafka import KafkaAdminClient

KAFKA_BROKERS = ["localhost:9092"]
DB_PATH = Path(r"d:\Cac_Cuoc_Thi\Seal_Hackathon_SU26\Smurf\services\database-saver\data\smurf_database.sqlite")

print("================================================================================")
print("🧹 BẮT ĐẦU XÓA SẠCH DỮ LIỆU RÁC/SIMULATOR ĐỂ ĐÓN DATA CHÍNH THỨC TỪ BTC")
print("================================================================================\n")

# 1. Reset SQLite Database
if DB_PATH.exists():
    try:
        os.remove(DB_PATH)
        print(f"✅ Đã xóa file Database cũ: {DB_PATH.name}")
    except Exception as e:
        print(f"⚠️ Không thể xóa file DB (có thể đang bị khóa): {e}")

# 2. Reset Redpanda Kafka Topics
TOPICS_TO_RESET = [
    "topic_raw", "topic_p", "topic_h", "topic_alerts", 
    "topic_forecasts", "topic_irrigation_plans", "topic_inspection_tasks", "topic_agent_logs"
]

try:
    admin = KafkaAdminClient(bootstrap_servers=KAFKA_BROKERS, request_timeout_ms=5000)
    existing_topics = admin.list_topics()
    
    topics_to_delete = [t for t in TOPICS_TO_RESET if t in existing_topics]
    
    if topics_to_delete:
        print(f"🗑️ Đang xóa các Topics Redpanda cũ: {topics_to_delete}...")
        admin.delete_topics(topics_to_delete)
        time.sleep(2)
        print("✅ Đã xóa sạch dữ liệu trên Redpanda Kafka Topics!")
    else:
        print("ℹ️ Các Topics đã sạch sẵn.")
        
    admin.close()
except Exception as e:
    print(f"⚠️ Lưu ý khi dọn dẹp Redpanda Topics: {e}")

print("\n================================================================================")
print("🎉 DỌN DẸP HOÀN TẤT! HỆ THỐNG ĐÃ SẠCH 100% ĐỂ SẴN SÀNG HỨNG DATA CHÍNH THỨC TỪ BTC")
print("================================================================================")
