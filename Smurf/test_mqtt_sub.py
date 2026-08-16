import json
import time
import paho.mqtt.client as mqtt

# BTC Contest MQTT Credentials
HOST = "broker.hivemq.com"  # Broker HiveMQ chính thức từ BTC
PORT = 1883
TOPIC = "hackathon/smurf/test/telemetry"
USERNAME = "SMURF"
PASSWORD = "mq_tlmUd5iH7C1_hyOdB0SKaA"

print("================================================================================")
print("📡 BẮT ĐẦU KẾT NỐI TEST MQTT BROKER BAN TỔ CHỨC HACKATHON")
print(f"🌐 Host: {HOST}:{PORT}")
print(f"🔑 Username: {USERNAME}")
print(f"📌 Topic Subscribed: {TOPIC}")
print("================================================================ algorithm ====================\n")

def on_connect(client, userdata, flags, rc, *args):
    if rc == 0:
        print("✅ KẾT NỐI THÀNH CÔNG! Đang lắng nghe dữ liệu Telemetry từ BTC...\n")
        client.subscribe(TOPIC)
    else:
        print(f"❌ Kết nối thất bại với mã lỗi return code rc = {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8', errors='ignore')
    print("--------------------------------------------------------------------------------")
    print(f"📩 [MESSAGE RECEIVED] Topic: {msg.topic}")
    try:
        data = json.loads(payload)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        print(f"Raw Content: {payload}")

# Support paho-mqtt v1.x and v2.x version compatibility
client_id = f"smurf-test-{int(time.time())}"
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
except AttributeError:
    client = mqtt.Client(client_id=client_id)

client.username_pw_set(USERNAME, PASSWORD)
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(HOST, PORT, keepalive=60)
    client.loop_forever()
except KeyboardInterrupt:
    print("\n👋 Đã dừng kiểm tra MQTT Listener.")
except Exception as e:
    print(f"❌ Lỗi kết nối: {e}")
