import os
from pydantic import BaseModel

class AISettings(BaseModel):
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    TOPIC_RAW: str = os.getenv("TOPIC_RAW", "topic_raw")
    TOPIC_P: str = os.getenv("TOPIC_P", "topic_p")
    TOPIC_H: str = os.getenv("TOPIC_H", "topic_h")
    TOPIC_FUZZY: str = os.getenv("TOPIC_FUZZY", "topic_fuzzy")
    TOPIC_PREDICT: str = os.getenv("TOPIC_PREDICT", "topic_predict")
    TOPIC_ALERTS: str = os.getenv("TOPIC_ALERTS", "topic_alerts")
    TOPIC_FORECASTS: str = os.getenv("TOPIC_FORECASTS", "topic_forecasts")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    AI_MODEL_NAME: str = os.getenv("AI_MODEL_NAME", "gemini-2.5-flash")

ai_settings = AISettings()
