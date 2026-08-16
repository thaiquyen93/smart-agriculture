import time
import ssl
import json
import paho.mqtt.client as mqtt

HOST = "mqtt-hackathon.lexatek.vn"
PORT = 443
USERNAME = "SMURF"
PASSWORD = "mq_tlmUd5iH7C1_hyOdB0SKaA"
TOPIC = "hackathon/smurf/test/telemetry"

print("================================================================================")
print("🔌 TESTING WSS CONNECTION TO BTC LEXATEK SERVER")
print(f"📡 Host: {HOST}:{PORT}")
print("================================================================================\n")

# Test paths: "/mqtt", "/", "/ws"
PATHS = ["/mqtt", "/", "/ws"]

def test_path(ws_path):
    print(f"\n🔍 Testing WebSocket path: '{ws_path}'...")
    
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"smurf-test-{int(time.time())}", transport="websockets")
    except AttributeError:
        client = mqtt.Client(client_id=f"smurf-test-{int(time.time())}", transport="websockets")

    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS)
    client.tls_insecure_set(True)
    client.ws_set_options(path=ws_path)

    connected = False

    def on_connect(c, u, f, rc, *args):
        nonlocal connected
        if rc == 0:
            connected = True
            print(f"  ✅ KẾT NỐI THÀNH CÔNG WSS VỚI PATH '{ws_path}'!")
            c.subscribe("hackathon/#")
            print(f"  📌 Subscribed to 'hackathon/#'")
        else:
            print(f"  ❌ Kết nối bị từ chối rc={rc}")

    def on_message(c, u, msg):
        print(f"\n  📩 [RECEIVED FROM BTC!] Topic: {msg.topic}")
        print(f"  Payload: {msg.payload.decode('utf-8', errors='ignore')}")

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(HOST, PORT, keepalive=30)
        client.loop_start()
        time.sleep(5)
        client.loop_stop()
        client.disconnect()
        return connected
    except Exception as e:
        print(f"  ❌ Connection error on path '{ws_path}': {e}")
        return False

for p in PATHS:
    if test_path(p):
        print(f"\n🎯 PATH ĐÚNG CỦA BTC LÀ: '{p}'")
        break
