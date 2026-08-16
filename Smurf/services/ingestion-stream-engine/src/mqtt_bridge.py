import json
import logging
import time
import os
import ssl
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from src.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Universal-MQTT-Bridge) %(message)s")
logger = logging.getLogger("mqtt_bridge")

class UniversalMQTTKafkaBridge:
    """
    Domain-Agnostic Universal MQTT Ingestion Bridge.
    Supports TCP, TLS, and WebSocket Secure (WSS) protocols (port 443).
    Automatically unpacks both single-device payloads and batch/nested BTC device arrays.
    """
    def __init__(self):
        client_id = f"smurf-bridge-{int(time.time())}"
        transport = "websockets" if settings.MQTT_BROKER_PORT == 443 or settings.MQTT_TRANSPORT == "websockets" else "tcp"
        
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id, transport=transport)
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id=client_id, transport=transport)
        
        # Configure TLS/WSS if port 443 or TLS enabled
        if settings.MQTT_BROKER_PORT == 443 or settings.MQTT_USE_TLS:
            self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
            self.mqtt_client.tls_insecure_set(True)
            if transport == "websockets" and settings.MQTT_WS_PATH:
                self.mqtt_client.ws_set_options(path=settings.MQTT_WS_PATH)
            logger.info(f"✓ Configured TLS / WSS transport (Path: {settings.MQTT_WS_PATH})")

        # Configure Authentication
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
            client.subscribe(settings.MQTT_TOPIC_WEATHER)
            logger.info(f"✓ Subscribed to MQTT Pattern: {settings.MQTT_TOPIC_WEATHER}")
        else:
            logger.error(f"❌ MQTT Connection failed with Return Code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload_bytes = msg.payload
            payload_str = payload_bytes.decode("utf-8", errors="ignore")
            
            try:
                data = json.loads(payload_str)
            except Exception:
                data = {"raw_payload": payload_str}

            now_epoch = float(data.get("epoch") or time.time())
            timestamp_str = data.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now_epoch))

            # Case A: BTC Nested Device Array payload (e.g. {"environment": "FARM", "devices": [...]})
            if isinstance(data.get("devices"), list):
                for dev in data["devices"]:
                    dev_code = dev.get("deviceCode") or dev.get("device_code") or "DEV_UNKNOWN"
                    metrics = dev.get("metrics", {})
                    
                    flattened = {
                        "device_code": dev_code,
                        "device_id": dev_code,
                        "station_id": dev_code,
                        "status": dev.get("status", "ok"),
                        "timestamp": now_epoch,
                        "event_time": now_epoch,
                        "timestamp_iso": timestamp_str,
                        "environment": data.get("environment", "FARM"),
                        "scenario": data.get("scenario", "NORMAL"),
                        "teamCode": data.get("teamCode", "SMURF"),
                        "protocol": "MQTT_WSS",
                        "mqtt_topic": msg.topic,
                        "ingestion_time": time.time(),
                        **metrics
                    }

                    if self.producer:
                        self.producer.send(settings.TOPIC_RAW, key=dev_code, value=flattened)
                        logger.debug(f"[MQTT WSS -> Redpanda] Dev: {dev_code} | Metrics: {metrics}")

            # Case B: Flat single-device telemetry format
            else:
                device_id = (
                    data.get("device_code") or
                    data.get("station_id") or 
                    data.get("device_id") or 
                    data.get("sensor_id") or 
                    data.get("id") or 
                    msg.topic.split("/")[-1] or 
                    "DEV_UNKNOWN"
                )
                data["device_id"] = device_id
                data["station_id"] = device_id
                data["protocol"] = "MQTT"
                data["mqtt_topic"] = msg.topic
                data["ingestion_time"] = time.time()
                if "event_time" not in data:
                    data["event_time"] = now_epoch
                if "timestamp" not in data:
                    data["timestamp"] = now_epoch

                if self.producer:
                    self.producer.send(settings.TOPIC_RAW, key=str(device_id), value=data)

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
