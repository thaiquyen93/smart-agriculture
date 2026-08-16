import socket

hosts = [
    "mqtt.seal-hackathon.io.vn",
    "broker.seal-hackathon.io.vn",
    "seal-hackathon.io.vn",
    "emqx.seal-hackathon.io.vn",
    "iot.seal-hackathon.io.vn",
    "hackathon.emqxsl.com",
    "hackathon.emqx.cloud",
    "broker.emqx.io",
]

print("🔍 Đang quét DNS tìm MQTT Broker Host...\n")
for h in hosts:
    try:
        ip = socket.getaddrinfo(h, 1883)[0][4][0]
        print(f"  ✅ {h} -> {ip}")
    except Exception:
        print(f"  ❌ {h} -> Không tồn tại")
