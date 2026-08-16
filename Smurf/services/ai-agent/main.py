import json
import logging
import time
from kafka import KafkaConsumer, KafkaProducer
from src.config import ai_settings
from src.fuzzy_engine import FuzzyLogicEngine
from src.predict_agent import PredictAgent
from src.inference_engine import OperationalInferenceEngine
from src.gemini_rewriter import GeminiHumanizerAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (AI-Agent-Microservice) %(message)s")
logger = logging.getLogger("ai_microservice")

class MultiAgentAIService:
    """
    Multi-Agent AI Microservice.
    Consumes from Redpanda TOPIC_P (minute aggregated windows) and TOPIC_RAW.
    Runs Fuzzy Logic -> Predict Agent -> Inference Engine -> Gemini Humanizer
    Publishes final output to TOPIC_FORECASTS and TOPIC_ALERTS.
    """
    def __init__(self):
        self.fuzzy_engine = FuzzyLogicEngine()
        self.predict_agent = PredictAgent()
        self.inference_engine = OperationalInferenceEngine()
        self.gemini_agent = GeminiHumanizerAgent()
        
        self.consumer = None
        self.producer = None
        self.is_running = False

    def init_kafka(self):
        retries = 20
        while retries > 0:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=ai_settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None
                )
                self.consumer = KafkaConsumer(
                    ai_settings.TOPIC_P,
                    bootstrap_servers=ai_settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    group_id="smurf-ai-agent-group",
                    auto_offset_reset="latest",
                    enable_auto_commit=True
                )
                logger.info(f"✓ AI Microservice connected to Redpanda Kafka: {ai_settings.KAFKA_BOOTSTRAP_SERVERS}")
                return
            except Exception as e:
                logger.warning(f"Waiting for Redpanda ({ai_settings.KAFKA_BOOTSTRAP_SERVERS})... {e}")
                time.sleep(2)
                retries -= 1
        logger.error("Failed to connect AI Microservice to Redpanda.")

    def run(self):
        self.init_kafka()
        self.is_running = True
        logger.info(f"🤖 Multi-Agent AI Service listening to Redpanda Topic: {ai_settings.TOPIC_P}...")

        try:
            for message in self.consumer:
                if not self.is_running:
                    break
                try:
                    aggregated_data = message.value
                    station_id = aggregated_data.get("station_id") or aggregated_data.get("device_id", "UNKNOWN")

                    # Step 1: Fuzzy Logic Evaluation
                    fuzzy_result = self.fuzzy_engine.evaluate_fuzzy_risk(aggregated_data)

                    # Step 2: Predict Agent Trend Forecasting
                    predict_result = self.predict_agent.predict_future_trend(aggregated_data, fuzzy_result)

                    # Step 3: Operational Inference Engine
                    inference_result = self.inference_engine.evaluate_inference(aggregated_data, fuzzy_result, predict_result)

                    # Step 4: Gemini LLM Humanizer Agent (Re-write technical report)
                    final_report = self.gemini_agent.humanize_report(inference_result, predict_result)

                    logger.info(f"🤖 [AI FORECAST GENERATED] Station: {station_id} -> {final_report.get('weather_condition')} (Risk: {final_report.get('risk_score')}/100)")

                    # Step 5: Publish final AI forecast back to Redpanda TOPIC_FORECASTS
                    if self.producer:
                        self.producer.send(ai_settings.TOPIC_FORECASTS, key=station_id, value=final_report)

                        # Emit alert if high risk
                        if final_report.get("risk_score", 0) >= 45:
                            alert_event = {
                                "station_id": station_id,
                                "severity": final_report.get("risk_level", "HIGH"),
                                "condition": final_report.get("weather_condition"),
                                "synoptic": final_report.get("synoptic_analysis"),
                                "decisions": final_report.get("smart_operational_decisions", []),
                                "created_at": time.time()
                            }
                            self.producer.send(ai_settings.TOPIC_ALERTS, key=station_id, value=alert_event)

                except Exception as e:
                    logger.error(f"Error in AI Multi-Agent pipeline: {e}")
        except KeyboardInterrupt:
            logger.info("AI Microservice stopped.")
        finally:
            if self.producer:
                self.producer.flush()
                self.producer.close()
            if self.consumer:
                self.consumer.close()

if __name__ == "__main__":
    ai_service = MultiAgentAIService()
    ai_service.run()
