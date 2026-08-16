from src import create_app
from src.services.mqtt_service import mqtt_service

from src.services.message_broker import broker

app = create_app()

if __name__ == '__main__':
    # Bắt đầu background thread lắng nghe MQTT
    mqtt_service.start()
    # Bắt đầu background thread lắng nghe Redpanda Kafka
    broker.start_consumer_thread()
    app.run(host='0.0.0.0', port=5000)
