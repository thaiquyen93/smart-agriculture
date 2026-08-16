"""
🌾 SMURF Farm IoT Simulator
Giả lập chính xác 6 thiết bị theo đề bài Track B: Smart Agriculture
Publish dữ liệu lên MQTT broker để phát triển pipeline AI + Dashboard

Devices:
  SOIL_01    - Cảm biến đất khu A     (soil_moisture %, temperature °C)
  WEATHER_01 - Trạm thời tiết         (temperature °C, humidity %)
  PUMP_01    - Bơm tưới khu A         (flow_rate L/min, power W)
  PH_01      - Cảm biến pH bồn        (ph)
  TANK_01    - Bồn nước chính          (level %)
  SUN_01     - Cảm biến nắng khu A    (lux lx)
"""

import json
import time
import random
import math
import paho.mqtt.client as mqtt

# ============================================================
# CẤU HÌNH MQTT (Giống hệt credentials BTC)
# ============================================================
HOST = "broker.hivemq.com"
PORT = 1883
TOPIC = "hackathon/smurf/test/telemetry"
USERNAME = "SMURF"
PASSWORD = "mq_tlmUd5iH7C1_hyOdB0SKaA"

# ============================================================
# MÔ HÌNH VẬT LÝ NÔNG TRẠI (Trạng thái ban đầu)
# ============================================================
class FarmState:
    """Trạng thái vật lý nông trại thay đổi theo thời gian thực."""
    def __init__(self):
        self.soil_moisture = 55.0       # % (Tối ưu cho rau: 40-70%)
        self.soil_temp = 26.0           # °C
        self.air_temp = 30.0            # °C
        self.air_humidity = 72.0        # %
        self.pump_running = False
        self.pump_flow_rate = 0.0       # L/min
        self.pump_power = 0.0           # W
        self.ph_value = 6.5             # pH (Tối ưu cho cây trồng: 6.0 - 7.0)
        self.tank_level = 85.0          # %
        self.sun_lux = 45000.0          # lux (Trời nắng ban ngày)
        self.tick = 0

    def advance(self):
        """Mô phỏng 1 bước thời gian (~5 giây thực)"""
        self.tick += 1
        hour_of_day = (time.localtime().tm_hour + time.localtime().tm_min / 60.0)

        # ---- Ánh sáng mặt trời theo giờ trong ngày ----
        if 6 <= hour_of_day <= 18:
            # Ban ngày: lux cao, đỉnh lúc 12h trưa
            sun_peak = math.sin(math.pi * (hour_of_day - 6) / 12)
            self.sun_lux = 15000 + 70000 * sun_peak + random.uniform(-2000, 2000)
        else:
            # Ban đêm: lux rất thấp
            self.sun_lux = random.uniform(0, 50)

        # ---- Nhiệt độ không khí theo giờ ----
        if 6 <= hour_of_day <= 14:
            self.air_temp = 24 + 10 * math.sin(math.pi * (hour_of_day - 6) / 16) + random.uniform(-0.5, 0.5)
        else:
            self.air_temp = 24 + 4 * math.cos(math.pi * (hour_of_day - 14) / 16) + random.uniform(-0.5, 0.5)

        # ---- Độ ẩm không khí (nghịch với nhiệt độ) ----
        self.air_humidity = max(40, min(98, 95 - self.air_temp * 0.8 + random.uniform(-2, 2)))

        # ---- Nhiệt độ đất (chậm hơn không khí) ----
        self.soil_temp += (self.air_temp - self.soil_temp) * 0.05 + random.uniform(-0.1, 0.1)

        # ---- Độ ẩm đất: giảm tự nhiên do bốc hơi, tăng khi bơm tưới ----
        evaporation = 0.08 * (self.air_temp / 30) * (self.sun_lux / 50000)
        self.soil_moisture -= evaporation + random.uniform(-0.05, 0.05)

        # ---- Logic bơm tưới tự động (khi đất khô < 35%) ----
        if self.soil_moisture < 35:
            self.pump_running = True
        elif self.soil_moisture > 65:
            self.pump_running = False

        if self.pump_running:
            self.pump_flow_rate = 12.0 + random.uniform(-1.5, 1.5)   # ~12 L/min
            self.pump_power = 750 + random.uniform(-30, 30)           # ~750W
            self.soil_moisture += 0.5 + random.uniform(0, 0.2)        # Tưới thì ẩm tăng
            self.tank_level -= 0.15 + random.uniform(0, 0.05)         # Bồn giảm
        else:
            self.pump_flow_rate = 0.0
            self.pump_power = 0.0

        # ---- pH dao động tự nhiên ----
        self.ph_value += random.uniform(-0.05, 0.05)
        self.ph_value = max(5.5, min(8.0, self.ph_value))

        # ---- Bồn nước: tự bổ sung chậm (giả lập nguồn cấp) ----
        if self.tank_level < 20:
            self.tank_level += 0.5  # Bổ sung khẩn cấp
        elif self.tank_level < 50:
            self.tank_level += 0.1  # Bổ sung chậm

        # Giới hạn giá trị hợp lệ
        self.soil_moisture = max(10, min(100, self.soil_moisture))
        self.tank_level = max(0, min(100, self.tank_level))
        self.sun_lux = max(0, self.sun_lux)


def build_payload(device_id, metrics, farm):
    """Tạo payload JSON giống format BTC."""
    payload = {
        "device_id": device_id,
        "timestamp": time.time(),
        "event_time": time.time(),
    }
    payload.update(metrics)
    return payload


def main():
    farm = FarmState()

    # Kết nối MQTT
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"smurf-sim-{int(time.time())}")
    except AttributeError:
        client = mqtt.Client(client_id=f"smurf-sim-{int(time.time())}")

    client.username_pw_set(USERNAME, PASSWORD)

    def on_connect(c, u, f, rc, *args):
        if rc == 0:
            print("✅ Simulator kết nối MQTT Broker thành công!")
        else:
            print(f"❌ Kết nối thất bại rc={rc}")

    client.on_connect = on_connect
    client.connect(HOST, PORT, keepalive=60)
    client.loop_start()
    time.sleep(1)

    print("=" * 70)
    print("🌾 SMURF FARM IOT SIMULATOR - TRACK B: SMART AGRICULTURE")
    print(f"📡 Broker: {HOST}:{PORT}")
    print(f"📌 Topic:  {TOPIC}")
    print(f"🔄 Chu kỳ: Mỗi 5 giây publish 6 thiết bị")
    print("=" * 70)

    DEVICES = [
        ("SOIL_01",    "Cảm biến đất khu A",  lambda f: {"soil_moisture": round(f.soil_moisture, 1), "temperature": round(f.soil_temp, 1)}),
        ("WEATHER_01", "Trạm thời tiết",       lambda f: {"temperature": round(f.air_temp, 1), "humidity": round(f.air_humidity, 1)}),
        ("PUMP_01",    "Bơm tưới khu A",       lambda f: {"flow_rate": round(f.pump_flow_rate, 1), "power": round(f.pump_power, 0), "status": "ON" if f.pump_running else "OFF"}),
        ("PH_01",      "Cảm biến pH bồn",      lambda f: {"ph": round(f.ph_value, 2)}),
        ("TANK_01",    "Bồn nước chính",        lambda f: {"level": round(f.tank_level, 1)}),
        ("SUN_01",     "Cảm biến nắng khu A",   lambda f: {"lux": round(f.sun_lux, 0)}),
    ]

    try:
        round_count = 0
        while True:
            round_count += 1
            farm.advance()

            print(f"\n📡 [Vòng {round_count}] {time.strftime('%H:%M:%S')} | "
                  f"Đất: {farm.soil_moisture:.1f}% | "
                  f"KK: {farm.air_temp:.1f}°C | "
                  f"Bồn: {farm.tank_level:.1f}% | "
                  f"Bơm: {'🟢 ON' if farm.pump_running else '⚪ OFF'} | "
                  f"Nắng: {farm.sun_lux:.0f} lux")

            for device_id, device_name, metric_fn in DEVICES:
                metrics = metric_fn(farm)
                payload = build_payload(device_id, metrics, farm)
                client.publish(TOPIC, json.dumps(payload))
                print(f"  📤 {device_id} ({device_name}): {metrics}")
                time.sleep(0.3)

            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\n👋 Simulator đã dừng.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
