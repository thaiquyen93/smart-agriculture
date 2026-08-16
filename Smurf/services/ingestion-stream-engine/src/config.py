import os
from pydantic import BaseModel

class Settings(BaseModel):
    # Redpanda / Kafka Cluster Settings
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    # Redpanda Topics Definition (Flexible for any contest domain)
    TOPIC_RAW: str = os.getenv("TOPIC_RAW", "topic_raw")
    TOPIC_P: str = os.getenv("TOPIC_P", "topic_p")             # 1-minute aggregated window (for Fuzzy AI / Anomaly)
    TOPIC_H: str = os.getenv("TOPIC_H", "topic_h")             # 1-hour aggregated window (for LLM / Trend AI)
    TOPIC_ALERTS: str = os.getenv("TOPIC_ALERTS", "topic_alerts")
    TOPIC_FORECASTS: str = os.getenv("TOPIC_FORECASTS", "topic_forecasts")

    # BTC MQTT Broker Configuration
    MQTT_BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "mqtt-hackathon.lexatek.vn")
    MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "443"))
    MQTT_TRANSPORT: str = os.getenv("MQTT_TRANSPORT", "websockets")
    MQTT_WS_PATH: str = os.getenv("MQTT_WS_PATH", "/mqtt")
    MQTT_USE_TLS: bool = os.getenv("MQTT_USE_TLS", "true").lower() in ("true", "1", "yes")
    MQTT_USERNAME: str = os.getenv("MQTT_USERNAME", "SMURF")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD", "mq_tlmUd5iH7C1_hyOdB0SKaA")
    MQTT_TOPIC_WEATHER: str = os.getenv("MQTT_TOPIC_WEATHER", "hackathon/smurf/test/telemetry")

    # Stream Processing Engine Configuration
    WATERMARK_DELAY_SECONDS: float = float(os.getenv("WATERMARK_DELAY_SECONDS", "5.0"))
    TUMBLING_WINDOW_SIZE_SEC: int = int(os.getenv("TUMBLING_WINDOW_SIZE_SEC", "60"))       # 1m
    SLIDING_WINDOW_SIZE_SEC: int = int(os.getenv("SLIDING_WINDOW_SIZE_SEC", "300"))       # 5m
    SLIDING_WINDOW_SLIDE_SEC: int = int(os.getenv("SLIDING_WINDOW_SLIDE_SEC", "60"))      # 1m slide
    HOURLY_WINDOW_SIZE_SEC: int = int(os.getenv("HOURLY_WINDOW_SIZE_SEC", "3600"))        # 1h

    # AI API Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "gemini-2.5-flash")

settings = Settings()
