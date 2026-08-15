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

class DatabaseSaverService:
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
                self.consumer.subscribe([TOPIC_RAW, TOPIC_P, TOPIC_H, TOPIC_FORECASTS])
                logger.info(f"✓ Database Saver connected to Redpanda Kafka: {KAFKA_BROKERS}")
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
                    dev_id = payload.get("device_id") or payload.get("station_id") or "UNKNOWN"

                    if topic == TOPIC_RAW:
                        self.db.save_raw(dev_id, payload)
                    elif topic in (TOPIC_P, TOPIC_H):
                        self.db.save_aggregated(dev_id, payload)
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
