import json
import logging
import uuid
import threading
import paho.mqtt.client as mqtt

from src.core.config import Config
from src.services.message_broker import broker

logger = logging.getLogger("mqtt_service")

class MQTTService:
    def __init__(self):
        self.client = None
        self.is_running = False
        self.topic = Config.MQTT_TOPIC_INPUT

    def on_connect(self, client, userdata, flags, rc, *args):
        if rc == 0:
            logger.info(f"Đã kết nối tới MQTT Broker tại {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
            client.subscribe(self.topic)
            logger.info(f"Đã subscribe vào MQTT topic: {self.topic}")
        else:
            logger.error(f"Kết nối MQTT thất bại với Return Code: {rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8")
            data = json.loads(payload_str)
            logger.info(f"Nhận data từ MQTT {msg.topic}")
            
            # Tránh circular import bằng cách import bên trong hàm hoặc lấy instance dùng chung
            from src.api.routes import predictive_service, fuzzy_agent
            
            predicted_values = {}
            # 1. Dự báo dữ liệu (Predictive)
            for field, values in data.items():
                if field not in predictive_service.sensor_fields:
                    continue
                    
                if not isinstance(values, list) or len(values) != 10:
                    logger.warning(f"Field '{field}' không có đủ 10 phần tử. Bỏ qua.")
                    continue
                    
                try:
                    predicted_val = predictive_service.predict(field, values)
                    predicted_values[field] = predicted_val
                except Exception as e:
                    logger.error(f"Lỗi dự báo cho field '{field}': {e}")

            if not predicted_values:
                logger.warning("Không có dữ liệu hợp lệ để xử lý mờ qua MQTT.")
                return

            # 2. Xử lý logic mờ (Fuzzy Logic) dựa trên kết quả DỰ BÁO
            fuzzy_input = predicted_values.copy()

            try:
                fuzzy_output = fuzzy_agent.process(fuzzy_input)
            except Exception as e:
                logger.error(f"Lỗi logic mờ: {e}")
                return

            task_id = str(uuid.uuid4())
            
            # 3. Đóng gói JSON Output
            result = {
                "task_id": task_id,
                "input_data": data,
                "predictive": predicted_values,
                "fuzzy": fuzzy_output,
                "source": "mqtt"
            }

            # 4. Publish ra Kafka Output Topic
            broker.publish_message(Config.OUTPUT_TOPIC, result)
            logger.info(f"Đã xử lý xong dữ liệu từ MQTT, đẩy kết quả ra Redpanda với task_id: {task_id}")

        except json.JSONDecodeError:
            logger.error("Dữ liệu MQTT không phải chuẩn JSON.")
        except Exception as e:
            logger.error(f"Lỗi xử lý message MQTT: {e}")

    def start(self):
        try:
            # Fallback to Version 1 behavior for older paho-mqtt
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"fuzzy-agent-{uuid.uuid4().hex[:8]}")
        except AttributeError:
            self.client = mqtt.Client(client_id=f"fuzzy-agent-{uuid.uuid4().hex[:8]}")
        
        if Config.MQTT_USERNAME:
            self.client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)
            
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        self.is_running = True
        
        def run_mqtt():
            try:
                self.client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, 60)
                self.client.loop_forever()
            except Exception as e:
                logger.error(f"Lỗi chạy MQTT client: {e}")
                
        thread = threading.Thread(target=run_mqtt, daemon=True)
        thread.start()
        logger.info("Đã khởi chạy MQTT consumer background thread.")

mqtt_service = MQTTService()
