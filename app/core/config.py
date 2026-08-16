import os

class Config:
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))

    # Redpanda/Kafka Configs
    REDPANDA_BROKERS = os.getenv('REDPANDA_BROKERS', 'localhost:9092')
    
    # Topics
    INPUT_TOPIC = os.getenv('INPUT_TOPIC', 'ai.input.topic')
    OUTPUT_TOPIC = os.getenv('OUTPUT_TOPIC', 'ai.output.topic')
    CONFIG_TOPIC = os.getenv('CONFIG_TOPIC', 'ai.config.topic')
