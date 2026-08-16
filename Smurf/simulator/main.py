import json
import logging
import math
import random
import time
from pathlib import Path
import paho.mqtt.client as mqtt
try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (AgriSimulator) %(message)s")
logger = logging.getLogger("simulator")

STATIONS_FILE = Path(__file__).parent / "data" / "stations.json"

KAFKA_BROKERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")
MQTT_BASE_TOPIC = os.getenv("MQTT_TOPIC_WEATHER", "hackathon/smurf/test/telemetry").rstrip("/#")
TOPIC_RAW = os.getenv("TOPIC_RAW", "topic_raw")

class SmartAgriSimulator:
    """
    Simulates 6 Smart Agriculture devices for SEAL Hackathon Track B:
    - SOIL_01: soil_moisture (%), temperature (°C)
    - WEATHER_01: temperature (°C), humidity (%)
    - PUMP_01: flow_rate (L/min), power (W)
    - PH_01: ph (pH)
    - TANK_01: level (%)
    - SUN_01: lux (lx)
    """
    def __init__(self):
        self.devices = self._load_devices()
        self.mqtt_client = mqtt.Client(client_id=f"smurf-agri-sim-{int(time.time())}", protocol=mqtt.MQTTv311)
        if MQTT_USER:
            self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
        self.kafka_producer = None
        self.is_running = False
        self.pump_active = False
        self.tank_level = 85.0
        self.soil_moisture = 42.0

    def _load_devices(self):
        if STATIONS_FILE.exists():
            with open(STATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return [
            {"device_code": "SOIL_01", "name": "Cảm biến đất khu A", "metrics": ["soil_moisture", "temperature"]},
            {"device_code": "WEATHER_01", "name": "Trạm thời tiết", "metrics": ["temperature", "humidity"]},
            {"device_code": "PUMP_01", "name": "Bơm tưới khu A", "metrics": ["flow_rate", "power"]},
            {"device_code": "PH_01", "name": "Cảm biến pH bồn", "metrics": ["ph"]},
            {"device_code": "TANK_01", "name": "Bồn nước chính", "metrics": ["level"]},
            {"device_code": "SUN_01", "name": "Cảm biến nắng khu A", "metrics": ["lux"]},
        ]

    def connect_mqtt(self):
        try:
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.mqtt_client.loop_start()
            logger.info(f"✓ Simulator connected to MQTT Broker ({MQTT_HOST}:{MQTT_PORT})")
        except Exception as e:
            logger.warning(f"Could not connect simulator to MQTT: {e}")

    def init_kafka(self):
        if KafkaProducer is None:
            return
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None
            )
            logger.info(f"✓ Simulator initialized fallback Kafka producer: {KAFKA_BROKERS}")
        except Exception as e:
            logger.warning(f"Kafka direct producer not available: {e}")

    def generate_device_reading(self, dev: dict) -> dict:
        now = time.time()
        code = dev["device_code"]
        payload = {
            "device_code": code,
            "device_id": code,
            "name": dev["name"],
            "timestamp": now,
            "event_time": now
        }

        if code == "SOIL_01":
            # Soil moisture slowly evaporates or increases if pump is active
            if self.pump_active:
                self.soil_moisture = min(80.0, self.soil_moisture + 0.8)
            else:
                self.soil_moisture = max(20.0, self.soil_moisture - 0.05 + random.uniform(-0.1, 0.1))
            payload["soil_moisture"] = round(self.soil_moisture, 1)
            payload["temperature"] = round(28.0 + random.uniform(-0.5, 0.5), 1)

        elif code == "WEATHER_01":
            payload["temperature"] = round(30.5 + random.uniform(-1.0, 1.0), 1)
            payload["humidity"] = round(68.0 + random.uniform(-3.0, 3.0), 1)

        elif code == "PUMP_01":
            if self.pump_active:
                payload["flow_rate"] = round(32.5 + random.uniform(-1.5, 1.5), 1)
                payload["power"] = round(850.0 + random.uniform(-20.0, 20.0), 1)
            else:
                payload["flow_rate"] = 0.0
                payload["power"] = 0.0

        elif code == "PH_01":
            payload["ph"] = round(6.5 + random.uniform(-0.15, 0.15), 2)

        elif code == "TANK_01":
            if self.pump_active:
                self.tank_level = max(5.0, self.tank_level - 0.2)
            else:
                self.tank_level = min(100.0, self.tank_level + 0.02)
            payload["level"] = round(self.tank_level, 1)

        elif code == "SUN_01":
            # Daylight curve simulation
            payload["lux"] = round(45000 + random.uniform(-2000, 3000), 0)

        return payload

    def run_loop(self, interval_sec: float = 2.0):
        self.is_running = True
        self.connect_mqtt()
        self.init_kafka()
        logger.info(f"🌾 Starting Smart Agriculture simulation for {len(self.devices)} devices (Interval: {interval_sec}s)...")

        iteration = 0
        while self.is_running:
            iteration += 1
            # Toggle pump every 30 iterations to simulate dynamic operations
            if iteration % 30 == 0:
                self.pump_active = not self.pump_active
                logger.info(f"⚙️ [SIMULATOR EVENT] Pump state changed: {'ON' if self.pump_active else 'OFF'}")

            for dev in self.devices:
                reading = self.generate_device_reading(dev)
                code = dev["device_code"]
                topic = f"{MQTT_BASE_TOPIC}/{code}"

                # 1. Publish to MQTT
                try:
                    self.mqtt_client.publish(topic, json.dumps(reading, ensure_ascii=False))
                    # Also publish to base telemetry topic for aggregated stream listeners
                    self.mqtt_client.publish(MQTT_BASE_TOPIC, json.dumps(reading, ensure_ascii=False))
                except Exception:
                    pass

                # 2. Publish to Kafka / Redpanda directly if available
                if self.kafka_producer:
                    try:
                        self.kafka_producer.send(TOPIC_RAW, key=code, value=reading)
                    except Exception:
                        pass

            time.sleep(interval_sec)

if __name__ == "__main__":
    sim = SmartAgriSimulator()
    sim.run_loop(interval_sec=2.0)
