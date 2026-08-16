import os
import time
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Tải file .env trong cùng thư mục
load_dotenv()

# Lấy các thông số từ biến môi trường
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")  # Thay bằng host thực tế
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "SMURF")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "mq_tlmUd5iH7C1_hyOdB0SKaA")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "hackathon/smurf/test/telemetry")
TEST_KEY = os.getenv("TEST_KEY", "tk_tYwpem7955kEiZeoQCeodvCGZp36XufO")

# Callback khi kết nối thành công
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"✅ Đã kết nối thành công tới MQTT Broker!")
        print(f"👉 Đang subscribe vào topic: {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Kết nối thất bại, mã lỗi: {rc}")

# Callback khi nhận được tin nhắn
def on_message(client, userdata, msg):
    print("\n" + "="*50)
    print(f"📥 Nhận được dữ liệu từ topic: {msg.topic}")
    print(f"📦 Nội dung (payload): {msg.payload.decode('utf-8')}")
    print("="*50)

def main():
    print("🚀 Bắt đầu MQTT Subscriber...")
    
    # Khởi tạo client
    client = mqtt.Client()
    
    # Set username và password
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"Đang kết nối tới {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Bắt đầu vòng lặp xử lý mạng
        client.loop_forever()
        
    except KeyboardInterrupt:
        print("\nĐã ngắt kết nối bởi người dùng.")
        client.disconnect()
    except Exception as e:
        print(f"Lỗi: {e}")

if __name__ == "__main__":
    main()
