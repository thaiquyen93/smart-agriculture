import argparse
import json
import os
import re
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Thiếu thư viện paho-mqtt. Cài bằng: pip install paho-mqtt python-dotenv")
    sys.exit(1)

KNOWN_DEVICES = {
    "SOIL_01": {"name": "Cảm biến đất khu A", "metrics": ["soil_moisture", "temperature"]},
    "WEATHER_01": {"name": "Trạm thời tiết", "metrics": ["temperature", "humidity"]},
    "PUMP_01": {"name": "Bơm tưới khu A", "metrics": ["flow_rate", "power"]},
    "PH_01": {"name": "Cảm biến pH bồn", "metrics": ["ph"]},
    "TANK_01": {"name": "Bồn nước chính", "metrics": ["level"]},
    "SUN_01": {"name": "Cảm biến nắng khu A", "metrics": ["lux"]},
}

DEVICE_CODE_PATTERN = re.compile(r"(SOIL|WEATHER|PUMP|PH|TANK|SUN)_\d+", re.IGNORECASE)

RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"


def colorize(text, code):
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"


def load_env_config(env_path):
    if load_dotenv and env_path.exists():
        load_dotenv(env_path)
    return {
        "host": os.getenv("MQTT_BROKER_HOST", "localhost"),
        "port": int(os.getenv("MQTT_BROKER_PORT", "1883")),
        "username": os.getenv("MQTT_USERNAME", ""),
        "password": os.getenv("MQTT_PASSWORD", ""),
        "topic": os.getenv("MQTT_TOPIC_WEATHER", ""),
    }


def detect_device(payload, topic):
    for key in ("device_code", "device_id", "sensor_id", "station_id", "id"):
        value = payload.get(key)
        if value and DEVICE_CODE_PATTERN.match(str(value)):
            return str(value).upper()
    match = DEVICE_CODE_PATTERN.search(topic)
    if match:
        return match.group(0).upper()
    last_segment = topic.split("/")[-1].upper()
    if DEVICE_CODE_PATTERN.match(last_segment):
        return last_segment
    for key in ("soil_moisture", "flow_rate", "ph", "level", "lux"):
        if key in payload:
            return {"soil_moisture": "SOIL_01", "flow_rate": "PUMP_01", "ph": "PH_01", "level": "TANK_01", "lux": "SUN_01"}[key]
    if {"temperature", "humidity"}.issubset(payload.keys()) and "lux" not in payload:
        return "WEATHER_01"
    return None


class MQTTProbe:
    def __init__(self, args):
        self.args = args
        self.env = load_env_config(Path(args.env))
        self.host = args.host or self.env["host"]
        self.port = args.port or self.env["port"]
        self.username = args.username if args.username is not None else self.env["username"]
        self.password = args.password if args.password is not None else self.env["password"]
        self.topic = args.topic or self.env["topic"] or "#"
        self.start_time = time.time()
        self.total_messages = 0
        self.unknown_payloads = 0
        self.topic_counts = defaultdict(int)
        self.device_stats = defaultdict(lambda: {"count": 0, "first_seen": None, "last_seen": None})
        self.seen_payload_keys = defaultdict(set)
        self.capture_file = None
        self.client = mqtt.Client(client_id=f"smurf-probe-{int(time.time())}", protocol=mqtt.MQTTv311)
        if self.username:
            self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(colorize(f"[OK] Đã kết nối MQTT {self.host}:{self.port}", GREEN))
            client.subscribe(self.topic, qos=0)
            print(colorize(f"[OK] Đang lắng nghe topic: {self.topic}", GREEN))
        elif rc == 5:
            print(colorize(f"[FAIL] Xác thực thất bại (rc={rc}). Sai username/password.", RED))
            self.client.disconnect()
        else:
            print(colorize(f"[FAIL] Không kết nối được (rc={rc}). Kiểm tra host/port/mạng.", RED))

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print(colorize(f"[WARN] Mất kết nối MQTT (rc={rc}). Đang thử lại...", YELLOW))

    def on_message(self, client, userdata, msg):
        self.total_messages += 1
        self.topic_counts[msg.topic] += 1
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        except (ValueError, UnicodeDecodeError):
            payload = {"raw_payload": msg.payload.decode("utf-8", errors="ignore")}
            self.unknown_payloads += 1

        device = detect_device(payload, msg.topic)
        now = time.time()
        if device:
            stats = self.device_stats[device]
            stats["count"] += 1
            if stats["first_seen"] is None:
                stats["first_seen"] = now
            stats["last_seen"] = now
        for key in payload.keys():
            self.seen_payload_keys[msg.topic].add(key)

        record = {
            "mqtt_topic": msg.topic,
            "device_code": device,
            "payload": payload,
            "capture_time": now,
            "capture_time_iso": datetime.fromtimestamp(now).isoformat(),
        }
        if self.capture_file:
            self.capture_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.capture_file.flush()

        self.print_message(msg.topic, device, payload)

    def print_message(self, topic, device, payload):
        if device:
            tag = colorize(device, CYAN)
        else:
            tag = colorize("CHƯA-XÁC-ĐỊNH", RED)
        summary = {k: v for k, v in payload.items() if k not in ("raw_payload",)}
        print(f"[{self.total_messages:>6}] {topic} -> {tag} | {json.dumps(summary, ensure_ascii=False)[:160]}")

    def print_report(self):
        elapsed = max(time.time() - self.start_time, 1)
        print("\n" + "=" * 72)
        print(colorize("BÁO CÁO KHẢO SÁT MQTT", BOLD))
        print("=" * 72)
        print(f"Thời gian chạy     : {elapsed:.0f}s")
        print(f"Tổng số bản tin    : {self.total_messages} ({self.total_messages / elapsed:.1f} msg/s)")
        print(f"Bản tin không phải JSON: {self.unknown_payloads}")
        print(f"Topic đã thấy      : {len(self.topic_counts)}")
        for topic, count in sorted(self.topic_counts.items()):
            print(f"  - {topic}  ({count} msg)")
        print("\n" + colorize("THIẾT BỊ NHẬN DIỆN (mục tiêu 4/6 hoặc 6/6):", BOLD))
        seen = 0
        for code, info in KNOWN_DEVICES.items():
            stats = self.device_stats.get(code)
            if stats and stats["count"] > 0:
                seen += 1
                first = datetime.fromtimestamp(stats["first_seen"]).strftime("%H:%M:%S")
                last = datetime.fromtimestamp(stats["last_seen"]).strftime("%H:%M:%S")
                print(colorize(f"  [X] {code} ({info['name']}) - {stats['count']} msg | đầu {first} | cuối {last}", GREEN))
            else:
                print(colorize(f"  [ ] {code} ({info['name']}) - CHƯA THẤY", YELLOW))
        print(f"\n=> Đạt {seen}/6 thiết bị theo tiêu chí chấm điểm (cần >= 4/6).")
        for code, stats in sorted(self.device_stats.items()):
            if code not in KNOWN_DEVICES:
                print(colorize(f"  [!] Thiết bị lạ: {code} - {stats['count']} msg", RED))
        print("\n" + colorize("CẤU TRÚC PAYLOAD (key trong từng topic):", BOLD))
        for topic in sorted(self.seen_payload_keys):
            keys = ", ".join(sorted(self.seen_payload_keys[topic]))
            print(f"  - {topic}: {keys}")
        if self.capture_file:
            print(f"\nDữ liệu thô đã lưu: {self.capture_file.name}")
        print("=" * 72)

    def run(self, duration):
        if self.args.capture:
            capture_dir = Path(self.args.capture)
            capture_dir.mkdir(parents=True, exist_ok=True)
            filename = capture_dir / f"mqtt_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
            self.capture_file = open(filename, "w", encoding="utf-8")
            print(colorize(f"Lưu dữ liệu thô vào: {filename}", GREEN))
        print(colorize(f"Kết nối {self.host}:{self.port} (user: {'<none>' if not self.username else self.username})...", CYAN))
        try:
            self.client.connect(self.host, self.port, keepalive=60)
        except Exception as e:
            print(colorize(f"[FAIL] Không kết nối được broker: {e}", RED))
            print("Kiểm tra: host/port đúng? BTC đã cấp credential chưa? Có cần VPN không?")
            sys.exit(1)
        self.client.loop_start()
        try:
            time.sleep(duration)
        except KeyboardInterrupt:
            pass
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            if self.capture_file:
                self.capture_file.close()
            self.print_report()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Smurf MQTT Probe - khảo sát broker MQTT của BTC, nhận diện 6 thiết bị nông trại và lưu dữ liệu thô.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", help="IP broker MQTT (mặc định: đọc từ .env)")
    parser.add_argument("--port", type=int, help="Port broker MQTT (mặc định: đọc từ .env)")
    parser.add_argument("--username", help="Username MQTT (mặc định: đọc từ .env)")
    parser.add_argument("--password", help="Password MQTT (mặc định: đọc từ .env)")
    parser.add_argument("--topic", help="Topic pattern để subscribe, dùng '#' để quét mọi topic (mặc định: #)")
    parser.add_argument("--env", default=str(Path(__file__).resolve().parent.parent / ".env"), help="Đường dẫn file .env")
    parser.add_argument("--capture", default=str(Path(__file__).resolve().parent.parent / "data" / "captures"), help="Thư mục lưu dữ liệu thô JSONL")
    parser.add_argument("--no-capture", action="store_true", help="Không lưu dữ liệu thô")
    parser.add_argument("--duration", type=int, default=60, help="Số giây chạy (Ctrl+C để dừng sớm)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.no_capture:
        args.capture = None
    probe = MQTTProbe(args)
    probe.run(args.duration)