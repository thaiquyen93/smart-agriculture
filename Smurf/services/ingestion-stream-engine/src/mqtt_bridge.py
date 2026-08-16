import json
import time
import logging
import os
import ssl
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from src.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Universal-MQTT-Bridge) %(message)s")
logger = logging.getLogger("mqtt_bridge")

class UniversalMQTTKafkaBridge:
    """
    Enterprise Domain-Agnostic MQTT to Redpanda Kafka Ingestion Bridge.
    Supports TCP, TLS, and WebSocket Secure (WSS) protocols (port 443).
    Automatically unpacks both flat payloads & BTC nested 'devices' array payloads.
    """
    def __init__(self):
        self.producer = None
        self.mqtt_client = None
        self.is_running = False

    def init_kafka(self):
        retries = 20
        while retries > 0:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: str(k).encode("utf-8") if k else None,
                    acks=1
                )
                logger.info(f"✓ Connected to Redpanda Kafka Cluster at {settings.KAFKA_BOOTSTRAP_SERVERS}")
                return
            except Exception as e:
                logger.warning(f"Waiting for Redpanda ({settings.KAFKA_BOOTSTRAP_SERVERS})... {e}")
                time.sleep(2)
                retries -= 1
        logger.error("Failed to connect MQTT Bridge to Redpanda after retries.")

    def on_connect(self, client, userdata, flags, rc, *args):
        if rc == 0:
            logger.info(f"✓ Connected to Contest MQTT Broker ({settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT})")
            client.subscribe(settings.MQTT_TOPIC_WEATHER)
            logger.info(f"✓ Subscribed to MQTT Topic Pattern: {settings.MQTT_TOPIC_WEATHER}")
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

            records_to_send = []

            # ------------------------------------------------------------------
            # FORMAT 1: Official BTC Nested 'devices' Array Payload
            # ------------------------------------------------------------------
            if "devices" in data and isinstance(data["devices"], list):
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
                        "teamCode": data.get("teamCode") or data.get("team_code") or "SMURF",
                        "protocol": "MQTT_WSS",
                        "mqtt_topic": msg.topic,
                        "ingestion_time": time.time(),
                    }
                    if isinstance(metrics, dict):
                        flattened.update(metrics)

                    records_to_send.append((dev_code, flattened))

            # ------------------------------------------------------------------
            # FORMAT 2: Flat Single Device Payload (Backward Compatible)
            # ------------------------------------------------------------------
            else:
                dev_id = (
                    data.get("device_code") or 
                    data.get("deviceCode") or 
                    data.get("station_id") or 
                    data.get("device_id") or 
                    msg.topic.split("/")[-1] or 
                    "DEV_UNKNOWN"
                )
                data["device_id"] = dev_id
                data["station_id"] = dev_id
                data["protocol"] = "MQTT"
                data["mqtt_topic"] = msg.topic
                data["ingestion_time"] = time.time()
                if "event_time" not in data:
                    data["event_time"] = now_epoch
                if "timestamp" not in data:
                    data["timestamp"] = now_epoch

                records_to_send.append((dev_id, data))

            # Forward all extracted records to Redpanda TOPIC_RAW
            if self.producer:
                for key_id, rec in records_to_send:
                    self.producer.send(
                        settings.TOPIC_RAW,
                        key=str(key_id),
                        value=rec
                    )
                    logger.debug(f"[MQTT -> Redpanda {settings.TOPIC_RAW}] Device: {key_id}")

        except Exception as e:
            logger.error(f"Error processing MQTT message from topic {msg.topic}: {e}")

    def start(self):
        self.init_kafka()
        self.is_running = True

        client_id = f"smurf-bridge-{int(time.time())}"
        is_wss = settings.MQTT_BROKER_PORT in (443, 8083, 8084) or "wss" in settings.MQTT_BROKER_HOST.lower() or settings.MQTT_TRANSPORT == "websockets"
        kwargs = {"transport": "websockets"} if is_wss else {}

        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id, **kwargs)
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id=client_id, **kwargs)

        if is_wss or settings.MQTT_USE_TLS:
            try:
                self.mqtt_client.tls_set(cert_reqs=ssl.CERT_NONE)
                self.mqtt_client.tls_insecure_set(True)
                ws_path = settings.MQTT_WS_PATH or "/mqtt"
                self.mqtt_client.ws_set_options(path=ws_path)
                logger.info(f"🔌 Using WebSocket Secure (WSS/TLS) transport protocol for MQTT (Path: {ws_path})")
            except Exception as e:
                logger.warning(f"Could not set websocket transport options: {e}")

        if settings.MQTT_USERNAME:
            self.mqtt_client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        host = settings.MQTT_BROKER_HOST.replace("wss://", "").replace("ws://", "").replace("http://", "").replace("https://", "").split("/")[0]

        logger.info(f"Connecting to Contest MQTT Broker at {host}:{settings.MQTT_BROKER_PORT}...")

        while self.is_running:
            try:
                self.mqtt_client.connect(host, settings.MQTT_BROKER_PORT, keepalive=60)
                self.mqtt_client.loop_forever()
            except Exception as e:
                logger.warning(f"MQTT Broker disconnected ({e}). Retrying in 5 seconds...")
                time.sleep(5)

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
