"""
🌾 SMURF Demo Suite - Shared Infrastructure
Module dùng chung cho các CLI giả lập kịch bản demo (M5.1).
Cung cấp:
  - Kết nối MQTT tự động (Local Mosquitto / Broker BTC WSS TLS)
  - Mô hình vật lý nông trại FarmPhysics có thể cấu hình
  - Hệ thống log màu ANSI và định dạng bảng chuẩn
  - Bộ tạo payload và vòng lặp publish
"""

import argparse
import json
import math
import os
import random
import re
import ssl
import sys
import time
from datetime import datetime
from pathlib import Path

# Đảm bảo UTF-8 trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Thiếu thư viện paho-mqtt. Cài bằng: pip install paho-mqtt python-dotenv")
    sys.exit(1)


# ============================================================
# MÀU SẮC ANSI & TIỆN ÍCH LOGGING
# ============================================================
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"


def colorize(text: str, code: str, no_color: bool = False) -> str:
    """Đổi màu chuỗi nếu môi trường hỗ trợ và không bật cờ --no-color."""
    if no_color or not sys.stdout.isatty():
        return str(text)
    return f"{code}{text}{RESET}"


def banner(title: str, subtitle: str = "", color: str = CYAN, no_color: bool = False):
    """In khung tiêu đề nổi bật cho kịch bản."""
    width = 75
    border = "=" * width
    print(colorize(f"\n{border}", color, no_color))
    print(colorize(f"🌾 {title.center(width - 4)}", BOLD + color, no_color))
    if subtitle:
        print(colorize(f"   {subtitle.center(width - 6)}", DIM + color, no_color))
    print(colorize(f"{border}\n", color, no_color))


def info(msg: str, no_color: bool = False):
    print(colorize(f"ℹ️  [INFO] {msg}", CYAN, no_color))


def success(msg: str, no_color: bool = False):
    print(colorize(f"✅ [SUCCESS] {msg}", GREEN, no_color))


def warn(msg: str, no_color: bool = False):
    print(colorize(f"⚠️  [WARN] {msg}", YELLOW, no_color))


def alert(msg: str, no_color: bool = False):
    print(colorize(f"🚨 [ALERT] {msg}", BOLD + RED, no_color))


def device_row(device_id: str, name: str, metrics: dict, is_alive: bool = True, no_color: bool = False) -> str:
    """Định dạng 1 dòng dữ liệu thiết bị xuất bản."""
    if not is_alive:
        tag = colorize("[OFFLINE/KILLED]", RED, no_color)
        return f"  📴 {colorize(device_id, DIM, no_color):<10} {name:<22}: {tag}"

    metric_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
    return f"  📤 {colorize(device_id, GREEN, no_color):<10} {name:<22}: {metric_str}"


# ============================================================
# CẤU HÌNH THIẾT BỊ NÔNG TRẠI
# ============================================================
ALL_DEVICE_DEFINITIONS = [
    {
        "id": "SOIL_01",
        "name": "Cảm biến đất khu A",
        "metric_fn": lambda f: {
            "soil_moisture": round(f.soil_moisture, 1),
            "temperature": round(f.soil_temp, 1),
        },
    },
    {
        "id": "WEATHER_01",
        "name": "Trạm thời tiết",
        "metric_fn": lambda f: {
            "temperature": round(f.air_temp, 1),
            "humidity": round(f.air_humidity, 1),
        },
    },
    {
        "id": "PUMP_01",
        "name": "Bơm tưới khu A",
        "metric_fn": lambda f: {
            "flow_rate": round(f.pump_flow_rate, 1),
            "power": round(f.pump_power, 0),
            "status": "ON" if f.pump_running else "OFF",
        },
    },
    {
        "id": "PH_01",
        "name": "Cảm biến pH bồn",
        "metric_fn": lambda f: {
            "ph": round(f.ph_value, 2),
        },
    },
    {
        "id": "TANK_01",
        "name": "Bồn nước chính",
        "metric_fn": lambda f: {
            "level": round(f.tank_level, 1),
        },
    },
    {
        "id": "SUN_01",
        "name": "Cảm biến nắng khu A",
        "metric_fn": lambda f: {
            "lux": round(f.sun_lux, 0),
        },
    },
]

KNOWN_DEVICE_IDS = [d["id"] for d in ALL_DEVICE_DEFINITIONS]


# ============================================================
# MÔ HÌNH VẬT LÝ NÔNG TRẠI ĐIỀU KHIỂN ĐƯỢC
# ============================================================
class FarmPhysics:
    """Mô hình vật lý nông trại thực tế, có các nút điều khiển kịch bản."""

    def __init__(
        self,
        soil_start: float = 55.0,
        soil_temp_start: float = 26.0,
        air_temp_start: float = 30.0,
        air_humidity_start: float = 72.0,
        tank_start: float = 85.0,
        ph_start: float = 6.5,
        pump_mode: str = "auto",  # 'auto', 'forced_off', 'forced_on'
        soil_freeze: float = None,  # Nếu set số thực, soil_moisture bị ghim quanh mức này (cho KB2)
        dry_multiplier: float = 1.0,  # Hệ số nhân tốc độ bốc hơi đất (đẩy nhanh cho KB1)
    ):
        self.soil_moisture = float(soil_start)
        self.soil_temp = float(soil_temp_start)
        self.air_temp = float(air_temp_start)
        self.air_humidity = float(air_humidity_start)
        self.tank_level = float(tank_start)
        self.ph_value = float(ph_start)
        self.sun_lux = 45000.0

        self.pump_mode = pump_mode
        self.soil_freeze = soil_freeze
        self.dry_multiplier = float(dry_multiplier)

        self.pump_running = False
        self.pump_flow_rate = 0.0
        self.pump_power = 0.0
        self.tick = 0

    def advance(self):
        """Mô phỏng 1 chu kỳ thời gian (mặc định ~5s thực)"""
        self.tick += 1
        now = time.localtime()
        hour_of_day = now.tm_hour + now.tm_min / 60.0 + now.tm_sec / 3600.0

        # 1. Diễn biến ánh sáng mặt trời theo giờ
        if 6 <= hour_of_day <= 18:
            sun_peak = math.sin(math.pi * (hour_of_day - 6) / 12)
            self.sun_lux = max(0.0, 15000 + 70000 * sun_peak + random.uniform(-2000, 2000))
        else:
            self.sun_lux = max(0.0, random.uniform(0, 50))

        # 2. Nhiệt độ không khí
        if 6 <= hour_of_day <= 14:
            self.air_temp = 24 + 10 * math.sin(math.pi * (hour_of_day - 6) / 16) + random.uniform(-0.3, 0.3)
        else:
            self.air_temp = 24 + 4 * math.cos(math.pi * (hour_of_day - 14) / 16) + random.uniform(-0.3, 0.3)

        # 3. Độ ẩm không khí (nghịch với nhiệt độ)
        self.air_humidity = max(40.0, min(98.0, 95.0 - self.air_temp * 0.8 + random.uniform(-1.5, 1.5)))

        # 4. Nhiệt độ đất (thay đổi chậm hơn không khí)
        self.soil_temp += (self.air_temp - self.soil_temp) * 0.05 + random.uniform(-0.05, 0.05)

        # 5. Logic điều khiển máy bơm
        if self.pump_mode == "forced_on":
            self.pump_running = True
        elif self.pump_mode == "forced_off":
            self.pump_running = False
        else:  # 'auto'
            if self.soil_moisture < 35.0:
                self.pump_running = True
            elif self.soil_moisture > 65.0:
                self.pump_running = False

        # 6. Thông số bơm & độ ẩm đất
        evaporation = 0.08 * (max(10.0, self.air_temp) / 30.0) * (max(100.0, self.sun_lux) / 50000.0) * self.dry_multiplier

        if self.pump_running:
            self.pump_flow_rate = max(0.0, 12.0 + random.uniform(-1.2, 1.2))  # ~12 L/min
            self.pump_power = max(0.0, 750.0 + random.uniform(-25.0, 25.0))  # ~750W
            self.tank_level -= 0.15 + random.uniform(0, 0.05)  # Bồn rút nước

            if self.soil_freeze is not None:
                # KB2: Bơm chạy nhưng đất bị lỗi/ghim, không tăng
                self.soil_moisture = float(self.soil_freeze) + random.uniform(-0.1, 0.1)
            else:
                self.soil_moisture += 0.5 + random.uniform(0, 0.2)
        else:
            self.pump_flow_rate = 0.0
            self.pump_power = 0.0

            if self.soil_freeze is not None:
                self.soil_moisture = float(self.soil_freeze) + random.uniform(-0.1, 0.1)
            else:
                self.soil_moisture -= evaporation + random.uniform(-0.04, 0.04)

        # 7. pH dao động tự nhiên
        self.ph_value += random.uniform(-0.03, 0.03)
        self.ph_value = max(5.5, min(8.0, self.ph_value))

        # 8. Bồn nước tự bổ sung nếu xuống quá thấp
        if self.tank_level < 20.0:
            self.tank_level += 0.5
        elif self.tank_level < 50.0 and not self.pump_running:
            self.tank_level += 0.1

        # 9. Giới hạn các đại lượng
        self.soil_moisture = max(5.0, min(100.0, self.soil_moisture))
        self.tank_level = max(0.0, min(100.0, self.tank_level))
        self.sun_lux = max(0.0, self.sun_lux)


# ============================================================
# CẤU HÌNH & KẾT NỐI MQTT
# ============================================================
def find_root_env() -> Path:
    """Tìm file .env ở thư mục gốc của repo."""
    current = Path(__file__).resolve()
    for parent in [current.parent, current.parent.parent, current.parent.parent.parent]:
        env_file = parent / ".env"
        if env_file.exists():
            return env_file
    return Path(".env")


def load_env_defaults(env_path: Path = None) -> dict:
    """Nạp cấu hình mặc định từ file .env nếu có."""
    if env_path is None:
        env_path = find_root_env()
    if load_dotenv and env_path.exists():
        load_dotenv(env_path)

    return {
        "host": os.getenv("MQTT_BROKER_HOST", "localhost"),
        "port": int(os.getenv("MQTT_BROKER_PORT", "1883")),
        "username": os.getenv("MQTT_USERNAME", ""),
        "password": os.getenv("MQTT_PASSWORD", ""),
        "topic": os.getenv("MQTT_TOPIC_WEATHER") or os.getenv("MQTT_TOPIC_TELEMETRY") or "hackathon/smurf/test/telemetry",
        "transport": os.getenv("MQTT_TRANSPORT", "tcp"),
        "ws_path": os.getenv("MQTT_WS_PATH", "/mqtt"),
        "use_tls": os.getenv("MQTT_USE_TLS", "false").lower() in ("true", "1", "yes"),
    }


def add_common_mqtt_args(parser: argparse.ArgumentParser):
    """Gắn các tham số CLI chung cho kết nối MQTT vào parser."""
    group = parser.add_argument_group("Cấu hình kết nối MQTT")
    group.add_argument("--local", action="store_true", help="Chạy nhanh với Mosquitto local (localhost:1883, plain TCP, không auth)")
    group.add_argument("--host", type=str, default=None, help="MQTT Broker host (mặc định lấy từ .env hoặc localhost)")
    group.add_argument("--port", type=int, default=None, help="MQTT Broker port (mặc định lấy từ .env hoặc 1883)")
    group.add_argument("--username", type=str, default=None, help="MQTT Username (mặc định lấy từ .env)")
    group.add_argument("--password", type=str, default=None, help="MQTT Password (mặc định lấy từ .env)")
    group.add_argument("--topic", type=str, default=None, help="MQTT Topic publish telemetry (mặc định lấy từ .env)")
    group.add_argument("--wss", action="store_true", help="Bắt buộc dùng WebSocket Secure (WSS) + TLS")
    group.add_argument("--ws-path", type=str, default=None, help="WebSocket path (mặc định: /mqtt)")
    group.add_argument("--env", type=str, default=None, help="Đường dẫn file .env tuỳ chọn")

    sim_group = parser.add_argument_group("Cấu hình mô phỏng & hiển thị")
    sim_group.add_argument("--interval", type=float, default=5.0, help="Chu kỳ publish (giây, mặc định: 5.0)")
    sim_group.add_argument("--duration-min", type=float, default=0.0, help="Thời gian chạy tối đa (phút, 0 = chạy vô hạn cho tới khi Ctrl+C)")
    sim_group.add_argument("--no-color", action="store_true", help="Tắt màu sắc trên console")

    agent_group = parser.add_argument_group("Cấu hình gửi yêu cầu tự động tới Agent Core (M5.1)")
    agent_group.add_argument(
        "--agent-core-url",
        type=str,
        default=os.getenv("AGENT_CORE_URL", "http://localhost:8100"),
        help="Base URL của agent-core (mặc định: http://localhost:8100, đọc từ env AGENT_CORE_URL nếu có)",
    )
    agent_group.add_argument(
        "--auto-send",
        dest="auto_send",
        action="store_true",
        default=True,
        help="Tự động gửi câu hỏi BTC + in Live Trace khi đạt điều kiện demo (mặc định: bật)",
    )
    agent_group.add_argument(
        "--no-auto-send",
        dest="auto_send",
        action="store_false",
        help="Tắt tự động gửi — chỉ in banner nhắc tay như trước (chế độ cũ)",
    )
    agent_group.add_argument(
        "--user-request",
        type=str,
        default=None,
        help="Ghi đè câu hỏi BTC mặc định của kịch bản gửi tới Agent Core",
    )


def create_mqtt_client(args: argparse.Namespace, client_id_prefix: str = "smurf-demo") -> tuple:
    """
    Khởi tạo MQTT Client phù hợp (tự động nhận diện WSS TLS hoặc Local TCP).
    Trả về: (client, final_host, final_port, final_topic, is_wss)
    """
    env_cfg = load_env_defaults(Path(args.env) if args.env else None)

    if args.local:
        host = "localhost"
        port = args.port or 1883
        username = ""
        password = ""
        topic = args.topic or "hackathon/smurf/test/telemetry"
        is_wss = False
        ws_path = "/mqtt"
    else:
        host = args.host or env_cfg["host"]
        port = args.port or env_cfg["port"]
        username = args.username if args.username is not None else env_cfg["username"]
        password = args.password if args.password is not None else env_cfg["password"]
        topic = args.topic or env_cfg["topic"]
        ws_path = args.ws_path or env_cfg["ws_path"]
        
        # Tự động xác định có dùng WSS hay không
        is_wss = (
            args.wss
            or port in (443, 8083, 8084)
            or "wss" in str(host).lower()
            or env_cfg.get("transport") == "websockets"
            or env_cfg.get("use_tls")
        )

    # Làm sạch host string (bỏ schema nếu người dùng gõ wss://...)
    clean_host = host.replace("wss://", "").replace("ws://", "").replace("http://", "").replace("https://", "").split("/")[0]

    client_id = f"{client_id_prefix}-{int(time.time())}"
    client_kwargs = {"transport": "websockets"} if is_wss else {}

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id, **client_kwargs)
    except AttributeError:
        client = mqtt.Client(client_id=client_id, **client_kwargs)

    if is_wss:
        try:
            client.tls_set(cert_reqs=ssl.CERT_NONE)
            client.tls_insecure_set(True)
            client.ws_set_options(path=ws_path)
        except Exception as e:
            warn(f"Cảnh báo TLS/WebSocket: {e}", getattr(args, "no_color", False))

    if username:
        client.username_pw_set(username, password)

    return client, clean_host, port, topic, is_wss


# ============================================================
# TẠO PAYLOAD CHUẨN FORMAT 2
# ============================================================
def build_payload(device_id: str, metrics: dict, farm: FarmPhysics = None) -> dict:
    """Tạo payload JSON chuẩn Format 2 phẳng (phù hợp với UniversalMQTTKafkaBridge)."""
    now = time.time()
    payload = {
        "device_id": device_id,
        "device_code": device_id,
        "timestamp": now,
        "event_time": now,
    }
    payload.update(metrics)
    return payload


# ============================================================
# TỰ ĐỘNG GỬI YÊU CẦU TỚI AGENT CORE (M5.1)
# ============================================================
def maybe_trigger_agent(args: argparse.Namespace, user_request: str, scenario_label: str, triggered_flag: list):
    """Gọi đúng 1 lần khi kịch bản vừa đạt điều kiện demo ("SẴN SÀNG DEMO").

    Nếu `--auto-send` (mặc định bật): spawn 1 thread daemon gửi câu hỏi BTC
    tới agent-core rồi in Live Trace — chạy SONG SONG với vòng lặp publish
    MQTT đang tiếp diễn (không dừng bơm dữ liệu, vì agent có thể xử lý tới
    hàng chục/trăm giây và freshness cần dữ liệu tiếp tục chảy).
    Nếu `--no-auto-send`: không làm gì (giữ hành vi cũ — chỉ banner nhắc tay).

    `triggered_flag` là 1 list 1 phần tử dùng làm cờ "đã kích hoạt chưa" do
    caller sở hữu, tránh gọi lặp lại ở các vòng lặp sau.
    """
    if triggered_flag[0]:
        return
    triggered_flag[0] = True

    if not getattr(args, "auto_send", True):
        return

    import threading

    from _agent_client import trigger_agent_and_print_trace

    final_request = getattr(args, "user_request", None) or user_request

    thread = threading.Thread(
        target=trigger_agent_and_print_trace,
        kwargs=dict(
            base_url=args.agent_core_url,
            user_request=final_request,
            scenario_label=scenario_label,
            no_color=getattr(args, "no_color", False),
        ),
        daemon=True,
    )
    thread.start()


# ============================================================
# VÒNG LẶP PUBLISH CHUNG
# ============================================================
def run_publish_loop(
    args: argparse.Namespace,
    physics: FarmPhysics,
    scenario_title: str,
    scenario_subtitle: str,
    on_tick_fn=None,
    filter_devices_fn=None,
):
    """
    Vòng lặp điều phối publish telemetry chung cho cả 3 kịch bản demo.
    """
    no_color = getattr(args, "no_color", False)
    client, host, port, topic, is_wss = create_mqtt_client(args, client_id_prefix="smurf-sim")

    connected_flag = [False]

    def on_connect(c, u, f, rc, *extra):
        if rc == 0:
            connected_flag[0] = True
            success(f"Kết nối MQTT Broker thành công ({host}:{port})!", no_color)
        elif rc == 5:
            alert(f"Lỗi xác thực MQTT (rc={rc}): Sai Username/Password!", no_color)
        else:
            alert(f"Lỗi kết nối MQTT (rc={rc}). Vui lòng kiểm tra Broker!", no_color)

    client.on_connect = on_connect

    banner(scenario_title, scenario_subtitle, color=CYAN, no_color=no_color)
    print(f"📡 Broker:    {colorize(f'{host}:{port}', BOLD, no_color)} ({'WSS/TLS' if is_wss else 'Plain TCP'})")
    print(f"📌 Topic:     {colorize(topic, BOLD, no_color)}")
    print(f"⏱️  Chu kỳ:    {args.interval}s")
    if args.duration_min > 0:
        print(f"⏳ Thời gian: Chạy trong {args.duration_min} phút")
    else:
        print(f"⏳ Thời gian: Chạy liên tục (Nhấn Ctrl+C để dừng)")
    print("-" * 75)

    try:
        client.connect(host, port, keepalive=60)
        client.loop_start()
    except Exception as e:
        alert(f"Không thể kết nối tới broker {host}:{port}: {e}", no_color)
        print("\n💡 Gợi ý: Nếu đang chạy offline, hãy thêm cờ `--local` để kết nối Mosquitto local (localhost:1883).")
        return

    time.sleep(0.5)

    start_time = time.time()
    round_count = 0

    try:
        while True:
            elapsed = time.time() - start_time
            if args.duration_min > 0 and elapsed >= (args.duration_min * 60):
                info(f"Đã hoàn thành thời gian chạy kịch bản ({args.duration_min} phút).", no_color)
                break

            round_count += 1
            physics.advance()

            # Gọi callback kiểm tra logic kịch bản riêng
            if on_tick_fn:
                on_tick_fn(round_count, elapsed, physics)

            # Lọc danh sách thiết bị còn sống / bị ngắt
            active_device_ids = set(KNOWN_DEVICE_IDS)
            if filter_devices_fn:
                active_device_ids = filter_devices_fn(elapsed, KNOWN_DEVICE_IDS)

            # In tóm tắt nông trại
            soil_color = GREEN if physics.soil_moisture >= 40 else (YELLOW if physics.soil_moisture >= 30 else RED)
            pump_status_str = colorize("🟢 ON", GREEN, no_color) if physics.pump_running else colorize("⚪ OFF", DIM, no_color)

            now_str = time.strftime("%H:%M:%S")
            print(
                f"\n📡 [Vòng {round_count:03d} | {elapsed:5.1f}s] {now_str} | "
                f"Đất: {colorize(f'{physics.soil_moisture:.1f}%', soil_color, no_color)} | "
                f"KK: {physics.air_temp:.1f}°C ({physics.air_humidity:.0f}%) | "
                f"Bồn: {physics.tank_level:.1f}% | "
                f"Bơm: {pump_status_str} | "
                f"Nắng: {physics.sun_lux:5.0f} lux"
            )

            # Xuất bản dữ liệu các thiết bị
            for dev in ALL_DEVICE_DEFINITIONS:
                dev_id = dev["id"]
                dev_name = dev["name"]
                is_alive = dev_id in active_device_ids

                if is_alive:
                    metrics = dev["metric_fn"](physics)
                    payload = build_payload(dev_id, metrics, physics)
                    client.publish(topic, json.dumps(payload), qos=0)
                    print(device_row(dev_id, dev_name, metrics, is_alive=True, no_color=no_color))
                else:
                    print(device_row(dev_id, dev_name, {}, is_alive=False, no_color=no_color))

                time.sleep(0.08)

            time.sleep(max(0.1, args.interval - 0.5))

    except KeyboardInterrupt:
        print("\n")
        warn("Nhận lệnh dừng từ người dùng (Ctrl+C). Đang đóng kết nối...", no_color)
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
        success("Đã dừng kịch bản an toàn.", no_color)
