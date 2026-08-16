import json
import time
import ssl
import paho.mqtt.client as mqtt

TOPIC = "hackathon/smurf/test/telemetry"
USERNAME = "SMURF"
PASSWORD = "mq_tlmUd5iH7C1_hyOdB0SKaA"

# Thử cả 2 host và 2 port (1883 plain, 8883 TLS)
CANDIDATES = [
    ("hackathon.emqxsl.com", 8883, True,  "EMQX Serverless TLS"),
    ("hackathon.emqxsl.com", 1883, False, "EMQX Serverless Plain"),
    ("broker.emqx.io",      1883, False, "EMQX Public Broker"),
]

def try_connect(host, port, use_tls, label):
    print(f"\n{'='*70}")
    print(f"🔌 [{label}] Đang thử kết nối {host}:{port} (TLS={'Có' if use_tls else 'Không'})...")

    def on_connect(client, userdata, flags, rc, *args):
        if rc == 0:
            print(f"  ✅ KẾT NỐI THÀNH CÔNG! -> {host}:{port}")
            client.subscribe(TOPIC)
            print(f"  📌 Đã subscribe topic: {TOPIC}")
            print(f"  ⏳ Chờ 8 giây xem có data từ BTC không...")
        else:
            rc_messages = {
                1: "Protocol version not supported",
                2: "Client ID rejected",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized",
            }
            print(f"  ❌ Kết nối bị từ chối! RC={rc}: {rc_messages.get(rc, 'Unknown')}")

    def on_message(client, userdata, msg):
        payload = msg.payload.decode('utf-8', errors='ignore')
        print(f"\n  📩 [DATA TỪ BTC!] Topic: {msg.topic}")
        try:
            data = json.loads(payload)
            print(f"  {json.dumps(data, indent=4, ensure_ascii=False)}")
        except:
            print(f"  Raw: {payload}")

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"smurf-scan-{int(time.time())}")
    except AttributeError:
        client = mqtt.Client(client_id=f"smurf-scan-{int(time.time())}")

    client.username_pw_set(USERNAME, PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    if use_tls:
        client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        client.tls_insecure_set(True)

    try:
        client.connect(host, port, keepalive=10)
        client.loop_start()
        time.sleep(8)
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        print(f"  ❌ Lỗi kết nối: {e}")

print("🔍 BẮT ĐẦU QUÉT 3 BROKER ĐỂ TÌM BROKER THẬT CỦA BTC...\n")

for host, port, use_tls, label in CANDIDATES:
    try_connect(host, port, use_tls, label)

print(f"\n{'='*70}")
print("✅ HOÀN TẤT QUÉT. Xem kết quả bên trên để xác định Broker thật của BTC!")
