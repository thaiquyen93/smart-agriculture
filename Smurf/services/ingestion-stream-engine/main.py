import threading
import time
import logging
from src.mqtt_bridge import MQTTKafkaBridge
from src.processor import StreamProcessingEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (Main-Launcher) %(message)s")
logger = logging.getLogger("main_launcher")

def run_mqtt_bridge():
    bridge = MQTTKafkaBridge()
    bridge.start()

def run_stream_processor():
    engine = StreamProcessingEngine()
    engine.run()

if __name__ == "__main__":
    logger.info("🚀 Launching Ingestion & Stream Processing Engine Microservice...")
    
    t1 = threading.Thread(target=run_mqtt_bridge, daemon=True)
    t2 = threading.Thread(target=run_stream_processor, daemon=True)
    
    t1.start()
    t2.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping microservice...")
