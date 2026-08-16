import pika
import json
import threading
import logging
from typing import Dict, Any
from app.core.config import Config
from app.agents.orchestrator import MultiAgentOrchestrator

logger = logging.getLogger(__name__)

class MessageBroker:
    """
    Quản lý kết nối RabbitMQ để nhận và gửi message.
    """
    def __init__(self):
        self.credentials = pika.PlainCredentials(Config.RABBITMQ_USER, Config.RABBITMQ_PASS)
        self.parameters = pika.ConnectionParameters(
            host=Config.RABBITMQ_HOST,
            port=Config.RABBITMQ_PORT,
            credentials=self.credentials
        )
        self.orchestrator = MultiAgentOrchestrator()

    def get_connection(self) -> pika.BlockingConnection:
        return pika.BlockingConnection(self.parameters)

    def publish_message(self, topic: str, message: Dict[str, Any]) -> None:
        try:
            connection = self.get_connection()
            channel = connection.channel()
            # Khai báo exchange (topic)
            channel.exchange_declare(exchange='ai_exchange', exchange_type='topic')
            
            channel.basic_publish(
                exchange='ai_exchange',
                routing_key=topic,
                body=json.dumps(message)
            )
            logger.info(f"Đã publish message tới topic '{topic}'")
            connection.close()
        except Exception as e:
            logger.error(f"Lỗi khi publish message: {e}")

    def start_consuming(self) -> None:
        def callback(ch, method, properties, body):
            logger.info(f"Nhận message từ topic: {method.routing_key}")
            try:
                data = json.loads(body)
                
                # Gọi luồng Multi-agent xử lý đầu vào
                result = self.orchestrator.process(data)
                
                # Publish kết quả đầu ra vào Topic
                self.publish_message(Config.OUTPUT_TOPIC, result)
            except json.JSONDecodeError:
                logger.error("Lỗi: Message nhận được không phải định dạng JSON hợp lệ.")
            except Exception as e:
                logger.error(f"Lỗi khi xử lý message: {e}")

        try:
            connection = self.get_connection()
            channel = connection.channel()
            channel.exchange_declare(exchange='ai_exchange', exchange_type='topic')
            
            # Tạo queue độc lập cho worker này
            result = channel.queue_declare(queue='', exclusive=True)
            queue_name = result.method.queue
            
            # Bind queue vào topic input
            channel.queue_bind(
                exchange='ai_exchange', 
                queue=queue_name, 
                routing_key=Config.INPUT_TOPIC
            )

            logger.info(f"[*] Đang chờ message ở topic '{Config.INPUT_TOPIC}'. Nhấn CTRL+C để thoát")
            channel.basic_consume(
                queue=queue_name, 
                on_message_callback=callback, 
                auto_ack=True
            )
            channel.start_consuming()
        except Exception as e:
            logger.error(f"Lỗi kết nối RabbitMQ: {e}")

    def start_consumer_thread(self) -> None:
        """Khởi chạy consumer trong một luồng riêng biệt để không block API Flask."""
        thread = threading.Thread(target=self.start_consuming, daemon=True)
        thread.start()
        logger.info("Đã khởi chạy RabbitMQ consumer background thread.")

broker = MessageBroker()
