import json
import threading
import logging
import os
from typing import Dict, Any
from src.core.config import Config

logger = logging.getLogger(__name__)

class MessageBroker:
    """
    Quản lý kết nối Redpanda (Kafka) để nhận và gửi message.
    """
    def __init__(self):
        self.brokers = Config.REDPANDA_BROKERS.split(',')
        self.producer = None
        self._init_producer()

    def _init_producer(self):
        try:
            from kafka import KafkaProducer
            self.producer = KafkaProducer(
                bootstrap_servers=self.brokers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Lỗi khởi tạo Redpanda Producer: {e}")

    def publish_message(self, topic: str, message: Dict[str, Any]) -> None:
        if self.producer:
            try:
                self.producer.send(topic, message)
                self.producer.flush()
                logger.info(f"Đã publish message tới Redpanda topic '{topic}'")
            except Exception as e:
                logger.error(f"Lỗi khi publish message lên Redpanda: {e}")
        else:
            logger.warning("Producer chưa được khởi tạo, không thể gửi message.")

    def process_config_message(self, data: Dict[str, Any]):
        """Xử lý cập nhật cấu hình/luật mờ động từ Redpanda."""
        logger.info(f"Đã nhận cấu hình mới từ Redpanda: {data}")
        if 'fuzzy_rules' in data:
            rules_path = os.path.join(os.path.dirname(__file__), '../fuzzy/rules.json')
            try:
                with open(rules_path, 'w', encoding='utf-8') as f:
                    json.dump(data['fuzzy_rules'], f, indent=4, ensure_ascii=False)
                logger.info("Đã cập nhật rules.json thành công từ Redpanda.")
            except Exception as e:
                logger.error(f"Lỗi khi lưu rules.json: {e}")

    def start_consuming(self) -> None:
        try:
            from kafka import KafkaConsumer
            consumer = KafkaConsumer(
                Config.INPUT_TOPIC,
                Config.CONFIG_TOPIC,
                bootstrap_servers=self.brokers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                group_id='ai_group',
                auto_offset_reset='latest'
            )
            logger.info(f"[*] Đang chờ message ở topics '{Config.INPUT_TOPIC}', '{Config.CONFIG_TOPIC}'.")
            
            for message in consumer:
                topic = message.topic
                data = message.value
                logger.info(f"Nhận message từ topic: {topic}")
                
                if topic == Config.CONFIG_TOPIC:
                    self.process_config_message(data)
                elif topic == Config.INPUT_TOPIC:
                    device_id = data.get("device_id")
                    metrics = data.get("metrics", {})
                    
                    if not device_id or not metrics:
                        continue
                        
                    fields = ['soil_moisture', 'temperature', 'humidity', 'flow_rate', 'power', 'ph', 'level', 'lux']
                    
                    if not hasattr(self, 'device_buffers'):
                        self.device_buffers = {}
                        
                    if device_id not in self.device_buffers:
                        self.device_buffers[device_id] = {f: [] for f in fields}
                        
                    buffer = self.device_buffers[device_id]
                    
                    # Cập nhật buffer trượt
                    for f in fields:
                        val = metrics.get(f"{f}_avg")
                        if val is not None:
                            buffer[f].append(val)
                            if len(buffer[f]) > 10:
                                buffer[f].pop(0)
                                
                    # Kiểm tra xem đã đủ 10 giá trị cho TẤT CẢ các trường chưa
                    is_ready = all(len(buffer[f]) == 10 for f in fields)
                    
                    if is_ready:
                        logger.info(f"Đã gom đủ 10 giá trị cho thiết bị {device_id}, tiến hành dự báo...")
                        
                        from src.api.routes import predictive_service, fuzzy_agent
                        import uuid
                        
                        predicted_values = {}
                        for field, values in buffer.items():
                            try:
                                predicted_val = predictive_service.predict(field, values)
                                predicted_values[field] = predicted_val
                            except Exception as e:
                                logger.error(f"Lỗi dự báo cho trường '{field}': {e}")
                                
                        if predicted_values:
                            fuzzy_input = predicted_values.copy()
                            try:
                                fuzzy_output = fuzzy_agent.process(fuzzy_input)
                                
                                result = {
                                    "task_id": str(uuid.uuid4()),
                                    "device_id": device_id,
                                    "input_data": {f: list(vals) for f, vals in buffer.items()},
                                    "predictive": predicted_values,
                                    "fuzzy": fuzzy_output,
                                    "source": "kafka_sliding_window"
                                }
                                
                                self.publish_message(Config.OUTPUT_TOPIC, result)
                                logger.info(f"Đã xử lý xong dữ liệu cho thiết bị {device_id} và publish lên Output Topic.")
                                
                            except Exception as e:
                                logger.error(f"Lỗi logic mờ: {e}")
                                
        except ImportError:
            logger.error("Thư viện 'kafka-python' chưa được cài đặt. Hãy chạy: pip install kafka-python")
        except Exception as e:
            logger.error(f"Lỗi kết nối Redpanda Consumer: {e}")

    def start_consumer_thread(self) -> None:
        """Khởi chạy consumer trong một luồng riêng biệt để không block ứng dụng."""
        thread = threading.Thread(target=self.start_consuming, daemon=True)
        thread.start()
        logger.info("Đã khởi chạy Redpanda consumer background thread.")

broker = MessageBroker()
