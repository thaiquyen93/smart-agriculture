import json
import logging
import math
import random
import time
from pathlib import Path
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Simulator) %(message)s")
logger = logging.getLogger("simulator")

STATIONS_FILE = Path(__file__).parent / "data" / "stations.json"

KAFKA_BROKERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
TOPIC_RAW = os.getenv("TOPIC_RAW", "topic_raw")

class WeatherSimulator:
    def __init__(self):
        self.stations = self._load_stations()
        self.mqtt_client = mqtt.Client(client_id="smurf-iot-simulator", protocol=mqtt.MQTTv311)
        self.kafka_producer = None
        self.current_scenario = "normal"
        self.is_running = False

    def _load_stations(self):
        if STATIONS_FILE.exists():
            with open(STATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return [
            {"station_id": "STN_HN_01", "station_name": "Hanoi Ba Dinh Station", "lat": 21.0338, "lon": 105.8286, "elevation_m": 12},
            {"station_id": "STN_HCM_02", "station_name": "HCMC District 1 Station", "lat": 10.7769, "lon": 106.7009, "elevation_m": 5},
            {"station_id": "STN_DN_03", "station_name": "Da Nang Radar Station", "lat": 16.0544, "lon": 108.2022, "elevation_m": 8},
            {"station_id": "STN_SP_04", "station_name": "Sa Pa Mountain Station", "lat": 22.3364, "lon": 103.8438, "elevation_m": 1500}
        ]

    def connect_mqtt(self):
        try:
            self.mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            self.mqtt_client.loop_start()
            logger.info(f"Simulator connected to MQTT Broker ({MQTT_HOST}:{MQTT_PORT})")
        except Exception as e:
            logger.warning(f"Could not connect simulator to MQTT: {e}")

    def init_kafka(self):
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None
            )
            logger.info(f"Simulator initialized fallback Kafka producer: {KAFKA_BROKERS}")
        except Exception as e:
            logger.warning(f"Kafka direct producer not available: {e}")

    def generate_station_reading(self, station: dict) -> dict:
        now = time.time()
        t_cycle = (now % 86400) / 86400 * 2 * math.pi
        diurnal_temp = math.sin(t_cycle - math.pi / 2) * 4.0
        
        temp = 28.0 + diurnal_temp + random.uniform(-0.5, 0.5)
        humidity = max(30.0, min(99.0, 75.0 - (diurnal_temp * 3) + random.uniform(-2, 2)))
        pressure = 1012.0 + random.uniform(-0.8, 0.8)
        wind_speed = max(0.5, 3.0 + random.uniform(-1.0, 2.0))
        rainfall = 0.0

        if self.current_scenario == "typhoon":
            pressure -= random.uniform(24.0, 30.0)
            wind_speed = random.uniform(20.0, 34.0)
            rainfall = random.uniform(50.0, 110.0)

        # Simulate 5% out-of-order delay for Watermark testing
        event_time = now
        if random.random() < 0.05:
            event_time = now - random.uniform(3.0, 8.0)

        return {
            "station_id": station["station_id"],
            "station_name": station["station_name"],
            "lat": station.get("lat", 0.0),
            "lon": station.get("lon", 0.0),
            "temp": round(temp, 2),
            "humidity": round(humidity, 1),
            "pressure": round(pressure, 2),
            "wind_speed": round(wind_speed, 2),
            "rainfall_mm_h": round(rainfall, 2),
            "pm25": round(random.uniform(10.0, 45.0), 1),
            "uv_index": round(random.uniform(1.0, 9.0), 1),
            "event_time": event_time,
            "created_at": now
        }

    def run_loop(self, interval_sec: float = 2.0):
        self.is_running = True
        self.connect_mqtt()
        self.init_kafka()
        logger.info(f"Starting weather simulation loop for {len(self.stations)} stations (Interval: {interval_sec}s)...")

        while self.is_running:
            for station in self.stations:
                reading = self.generate_station_reading(station)
                station_id = station["station_id"]
                topic = f"iot/weather/{station_id}"
                
                try:
                    self.mqtt_client.publish(topic, json.dumps(reading))
                except Exception:
                    pass

                if self.kafka_producer:
                    try:
                        self.kafka_producer.send(TOPIC_RAW, key=station_id, value=reading)
                    except Exception:
                        pass
            time.sleep(interval_sec)

if __name__ == "__main__":
    sim = WeatherSimulator()
    sim.run_loop(interval_sec=2.0)
