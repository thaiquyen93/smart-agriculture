import json
import logging
import time
from typing import Dict, Any
from kafka import KafkaConsumer, KafkaProducer
from src.config import settings
from src.watermark import WatermarkManager
from src.windowing import WindowManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Stream-Engine) %(message)s")
logger = logging.getLogger("stream_processor")

class StreamProcessingEngine:
    """
    Core Enterprise Stream Processing Engine.
    Handles Watermarking, Tumbling/Sliding/Hourly Windowing, and publishes:
    - TOPIC_P (minute aggregated windows) -> For Fuzzy & Predict AI
    - TOPIC_H (hourly aggregated windows) -> For LLM & Macro RAG
    """
    def __init__(self):
        self.watermark_mgr = WatermarkManager(max_out_of_orderness_sec=settings.WATERMARK_DELAY_SECONDS)
        self.window_mgr = WindowManager(
            tumbling_size_sec=settings.TUMBLING_WINDOW_SIZE_SEC,
            sliding_size_sec=settings.SLIDING_WINDOW_SIZE_SEC,
            sliding_step_sec=settings.SLIDING_WINDOW_SLIDE_SEC,
            hourly_size_sec=settings.HOURLY_WINDOW_SIZE_SEC
        )
        self.consumer = None
        self.producer = None
        self.is_running = False

    def init_kafka(self):
        retries = 20
        while retries > 0:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None
                )
                self.consumer = KafkaConsumer(
                    settings.TOPIC_RAW,
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    group_id="smurf-stream-processing-group",
                    auto_offset_reset="latest",
                    enable_auto_commit=True
                )
                logger.info(f"Stream Engine connected to Redpanda Kafka: {settings.KAFKA_BOOTSTRAP_SERVERS}")
                return
            except Exception as e:
                logger.warning(f"Waiting for Redpanda ({settings.KAFKA_BOOTSTRAP_SERVERS})... {e}")
                time.sleep(2)
                retries -= 1
        logger.error("Could not connect Stream Engine to Redpanda.")

    def process_raw_event(self, record: Dict[str, Any]):
        station_id = record.get("station_id", "STN_UNKNOWN")
        is_on_time, event_time, current_watermark = self.watermark_mgr.process_event(record)

        if is_on_time:
            self.window_mgr.assign_tumbling_window(station_id, record, event_time)
            self.window_mgr.assign_sliding_window(station_id, record, event_time)
            self.window_mgr.assign_hourly_window(station_id, record, event_time)
        else:
            logger.info(f"[LATE DATA DROPPED FROM WINDOW] Station: {station_id}, EventTime: {event_time:.1f}, Watermark: {current_watermark:.1f}")

        # Check and trigger window closings
        emitted_windows = self.window_mgr.advance_watermark_and_trigger(current_watermark)
        for agg in emitted_windows:
            self._handle_aggregated_window(agg)

    def _handle_aggregated_window(self, agg: Dict[str, Any]):
        station_id = agg.get("station_id")
        win_type = agg.get("window_type", "TUMBLING_1M")
        duration = agg.get("window_duration_sec", 60)
        anomalies = agg.get("anomalies", [])

        metrics_summary = list(agg.get("metrics", {}).keys())
        logger.info(f"[WINDOW CLOSED: {win_type}] Station: {station_id} | Metrics ({len(metrics_summary)}): {metrics_summary} | Anomalies: {len(anomalies)}")

        if not self.producer:
            return

        # Route to appropriate topic: TOPIC_P (minute/sliding) vs TOPIC_H (hourly)
        if duration >= 3600 or win_type == "HOURLY_1H":
            self.producer.send(settings.TOPIC_H, key=station_id, value=agg)
            logger.info(f"📊 [PUBLISHED -> {settings.TOPIC_H}] Station: {station_id} (1-Hour Window)")
        else:
            self.producer.send(settings.TOPIC_P, key=station_id, value=agg)
            logger.info(f"⚡ [PUBLISHED -> {settings.TOPIC_P}] Station: {station_id} (Minute Window)")

        # Emit alert if severe anomalies present
        if len(anomalies) > 0:
            alert = {
                "station_id": station_id,
                "station_name": agg.get("station_name"),
                "window_type": win_type,
                "anomalies": anomalies,
                "created_at": time.time()
            }
            self.producer.send(settings.TOPIC_ALERTS, key=station_id, value=alert)

    def run(self):
        self.init_kafka()
        self.is_running = True
        logger.info(f"Starting Stream Processing Engine loop (Listening to {settings.TOPIC_RAW})...")

        try:
            for message in self.consumer:
                if not self.is_running:
                    break
                try:
                    record = message.value
                    self.process_raw_event(record)
                except Exception as e:
                    logger.error(f"Error processing record from Redpanda: {e}")
        except KeyboardInterrupt:
            logger.info("Stream Engine interrupted.")
        finally:
            if self.producer:
                self.producer.flush()
                self.producer.close()
            if self.consumer:
                self.consumer.close()

if __name__ == "__main__":
    engine = StreamProcessingEngine()
    engine.run()
