import json
import logging
import time
import os
from kafka import KafkaConsumer
from db import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Database-Saver) %(message)s")
logger = logging.getLogger("db_saver")

KAFKA_BROKERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_RAW = os.getenv("TOPIC_RAW", "topic_raw")
TOPIC_P = os.getenv("TOPIC_P", "topic_p")
TOPIC_H = os.getenv("TOPIC_H", "topic_h")
TOPIC_FORECASTS = os.getenv("TOPIC_FORECASTS", "topic_forecasts")
TOPIC_IRRIGATION_PLANS = os.getenv("TOPIC_IRRIGATION_PLANS", "topic_irrigation_plans")
TOPIC_INSPECTION_TASKS = os.getenv("TOPIC_INSPECTION_TASKS", "topic_inspection_tasks")
TOPIC_AGENT_LOGS = os.getenv("TOPIC_AGENT_LOGS", "topic_agent_logs")

class DatabaseSaverService:
    """
    Enterprise Database Saver Microservice for Track B.
    Listens to Kafka topics and persists raw telemetry, aggregated windows,
    irrigation plans, inspection tasks, and multi-agent reasoning traces into SQLite.
    """
    def __init__(self):
        self.db = DatabaseManager()
        self.consumer = None
        self.is_running = False

    def init_kafka(self):
        retries = 20
        while retries > 0:
            try:
                self.consumer = KafkaConsumer(
                    bootstrap_servers=KAFKA_BROKERS.split(","),
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    group_id="smurf-db-saver-group",
                    auto_offset_reset="latest",
                    enable_auto_commit=True
                )
                topics = [
                    TOPIC_RAW, TOPIC_P, TOPIC_H, TOPIC_FORECASTS,
                    TOPIC_IRRIGATION_PLANS, TOPIC_INSPECTION_TASKS, TOPIC_AGENT_LOGS
                ]
                self.consumer.subscribe(topics)
                logger.info(f"✓ Database Saver connected to Redpanda Kafka: {KAFKA_BROKERS}")
                logger.info(f"📌 Subscribed to Kafka Topics: {topics}")
                return
            except Exception as e:
                logger.warning(f"Waiting for Redpanda ({KAFKA_BROKERS})... {e}")
                time.sleep(2)
                retries -= 1
        logger.error("Failed to connect Database Saver to Redpanda.")

    def run(self):
        self.init_kafka()
        self.is_running = True
        logger.info("💾 Database Saver Service running & storing historical logs...")

        try:
            for message in self.consumer:
                if not self.is_running:
                    break
                try:
                    topic = message.topic
                    payload = message.value
                    dev_id = payload.get("device_id") or payload.get("station_id") or "DEV_UNKNOWN"

                    if topic == TOPIC_RAW:
                        self.db.save_raw(dev_id, payload, topic_name=topic)
                    elif topic in (TOPIC_P, TOPIC_H):
                        self.db.save_aggregated(dev_id, payload, topic_name=topic)
                    elif topic == TOPIC_IRRIGATION_PLANS:
                        self.db.save_irrigation_plan(payload)
                    elif topic == TOPIC_INSPECTION_TASKS:
                        self.db.save_inspection_task(payload)
                    elif topic == TOPIC_AGENT_LOGS:
                        self.db.save_agent_log(
                            session_id=payload.get("session_id", "DEFAULT_SESSION"),
                            agent_name=payload.get("agent_name", "UnknownAgent"),
                            action_type=payload.get("action_type", "REASONING"),
                            output_response=payload.get("output_response", ""),
                            input_prompt=payload.get("input_prompt", ""),
                            evidence_data=payload.get("evidence_data")
                        )
                    elif topic == TOPIC_FORECASTS:
                        self.db.save_forecast(dev_id, payload)
                except Exception as e:
                    logger.error(f"Error saving message from topic {message.topic}: {e}")
        except KeyboardInterrupt:
            logger.info("Database Saver stopped.")
        finally:
            if self.consumer:
                self.consumer.close()

if __name__ == "__main__":
    service = DatabaseSaverService()
    service.run()
