import json
import logging
import time
import os
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from src.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Universal-MQTT-Bridge) %(message)s")
logger = logging.getLogger("mqtt_bridge")

class UniversalMQTTKafkaBridge:
    """
    Domain-Agnostic Universal MQTT Ingestion Bridge.
    Connects to ANY Contest MQTT Broker (Supports Auth, Custom Topics, TLS)
    and forwards raw IoT telemetry payloads directly to Redpanda TOPIC_RAW.
    """
    def __init__(self):
        client_id = f"smurf-bridge-{int(time.time())}"
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id=client_id)
        
        # Configure Authentication if provided by Contest Organizers (BTC)
        if settings.MQTT_USERNAME and settings.MQTT_PASSWORD:
            self.mqtt_client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
            logger.info(f"Configured MQTT Authentication for user: {settings.MQTT_USERNAME}")
            
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.producer = None
        self.is_running = False

    def init_kafka(self):
        retries = 20
        while retries > 0:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                    retries=5
                )
                logger.info(f"✓ Connected to Redpanda Kafka Cluster at {settings.KAFKA_BOOTSTRAP_SERVERS}")
                return
            except Exception as e:
                logger.warning(f"Waiting for Redpanda ({settings.KAFKA_BOOTSTRAP_SERVERS})... {e}")
                time.sleep(2)
                retries -= 1
        logger.error("Failed to connect MQTT Bridge to Redpanda after retries.")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"✓ Connected to Contest MQTT Broker ({settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT})")
            # Subscribe to contest topic wildcard pattern
            client.subscribe(settings.MQTT_TOPIC_WEATHER)
            logger.info(f"✓ Subscribed to MQTT Pattern: {settings.MQTT_TOPIC_WEATHER}")
        else:
            logger.error(f"❌ MQTT Connection failed with Return Code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload_bytes = msg.payload
            payload_str = payload_bytes.decode("utf-8", errors="ignore")
            
            # Extract JSON data
            try:
                data = json.loads(payload_str)
            except Exception:
                data = {"raw_payload": payload_str}

            # Domain-Agnostic Device ID Extraction (works for weather, traffic, factory, energy, etc.)
            device_id = (
                data.get("station_id") or 
                data.get("device_id") or 
                data.get("sensor_id") or 
                data.get("id") or 
                data.get("uuid") or 
                msg.topic.split("/")[-1] or 
                "DEV_UNKNOWN"
            )
            
            # Enrich generic ingestion metadata
            data["device_id"] = device_id
            data["station_id"] = device_id  # Alias for backward compatibility
            data["protocol"] = "MQTT"
            data["mqtt_topic"] = msg.topic
            data["ingestion_time"] = time.time()
            if "event_time" not in data:
                data["event_time"] = time.time()

            # Forward immediately to Redpanda TOPIC_RAW
            if self.producer:
                self.producer.send(
                    settings.TOPIC_RAW,
                    key=str(device_id),
                    value=data
                )
                logger.debug(f"[MQTT -> Redpanda {settings.TOPIC_RAW}] Device: {device_id}")
        except Exception as e:
            logger.error(f"Error processing MQTT message from topic {msg.topic}: {e}")

    def start(self):
        self.init_kafka()
        self.is_running = True
        logger.info(f"Connecting to Contest MQTT Broker at {settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT}...")
        
        while self.is_running:
            try:
                self.mqtt_client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=60)
                self.mqtt_client.loop_forever()
            except Exception as e:
                logger.warning(f"MQTT connection drop: {e}. Reconnecting in 3s...")
                time.sleep(3)

    def stop(self):
        self.is_running = False
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        if self.producer:
            self.producer.flush()
            self.producer.close()
        logger.info("Universal MQTT Bridge stopped.")

if __name__ == "__main__":
    bridge = UniversalMQTTKafkaBridge()
    bridge.start()
