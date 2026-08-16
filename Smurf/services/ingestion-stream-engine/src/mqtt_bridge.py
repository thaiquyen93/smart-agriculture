import json
import time
import logging
import os
import dateutil.parser
import paho.mqtt.client as mqtt
from kafka import KafkaProducer
from src.config import settings

logger = logging.getLogger("mqtt_bridge")

class UniversalMQTTKafkaBridge:
    """
    Enterprise MQTT to Redpanda Kafka Ingestion Bridge.
    Supports official Hackathon Simulator protocol:
      - Host: mqtt-hackathon.lexatek.vn (Port 443 WSS or Port 1883/8883)
      - Dynamic JSON Payload Extractor: Handles both flat payloads & BTC nested 'devices' array payloads.
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
            logger.info(f"✓ Connected to BTC Contest MQTT Broker ({settings.MQTT_BROKER_HOST}:{settings.MQTT_BROKER_PORT})")
            client.subscribe(settings.MQTT_TOPIC_WEATHER)
            logger.info(f"✓ Subscribed to MQTT Topic Pattern: {settings.MQTT_TOPIC_WEATHER}")
        else:
            logger.error(f"❌ MQTT Connection failed with Return Code: {rc}")

    def _parse_iso_timestamp(self, ts_str: str) -> float:
        """Parses ISO 8601 string '2026-08-16T01:00:00.000Z' to epoch timestamp."""
        try:
            dt = dateutil.parser.isoparse(ts_str)
            return dt.timestamp()
        except Exception:
            return time.time()

    def on_message(self, client, userdata, msg):
        try:
            payload_bytes = msg.payload
            payload_str = payload_bytes.decode("utf-8", errors="ignore")
            
            try:
                data = json.loads(payload_str)
            except Exception:
                data = {"raw_payload": payload_str}

            # Parse event time from timestamp field
            raw_ts = data.get("timestamp")
            if isinstance(raw_ts, str):
                event_time = self._parse_iso_timestamp(raw_ts)
            elif isinstance(raw_ts, (int, float)):
                event_time = float(raw_ts)
            else:
                event_time = time.time()

            records_to_send = []

            # ------------------------------------------------------------------
            # FORMAT 1: Official BTC Nested 'devices' Array Payload
            # Example: {"timestamp": "...", "teamCode": "...", "devices": [{ "deviceCode": "TEMP_001", "metrics": {...} }]}
            # ------------------------------------------------------------------
            if "devices" in data and isinstance(data["devices"], list):
                for dev in data["devices"]:
                    dev_code = dev.get("deviceCode") or dev.get("device_code") or "DEV_UNKNOWN"
                    metrics = dev.get("metrics", {})
                    
                    rec = {
                        "device_id": dev_code,
                        "station_id": dev_code,
                        "device_code": dev_code,
                        "status": dev.get("status", "ok"),
                        "environment": data.get("environment", "DEFAULT"),
                        "team_code": data.get("teamCode") or data.get("team_code"),
                        "protocol": "MQTT",
                        "mqtt_topic": msg.topic,
                        "event_time": event_time,
                        "ingestion_time": time.time()
                    }
                    # Flatten metrics object directly into record
                    if isinstance(metrics, dict):
                        rec.update(metrics)
                    
                    records_to_send.append((dev_code, rec))

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
                data["event_time"] = event_time
                data["ingestion_time"] = time.time()

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
        is_wss = settings.MQTT_BROKER_PORT in (443, 8083, 8084) or "wss" in settings.MQTT_BROKER_HOST.lower()
        kwargs = {"transport": "websockets"} if is_wss else {}

        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id, **kwargs)
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id=client_id, **kwargs)

        if is_wss:
            try:
                import ssl
                self.mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
                self.mqtt_client.tls_insecure_set(True)
                self.mqtt_client.ws_set_options(path="/mqtt")
                logger.info("🔌 Using WebSocket Secure (WSS/TLS) transport protocol for MQTT connection")
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
