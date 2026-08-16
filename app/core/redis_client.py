import redis
from app.core.config import Config

class RedisClient:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            pool = redis.ConnectionPool(
                host=Config.REDIS_HOST,
                port=Config.REDIS_PORT,
                db=Config.REDIS_DB,
                decode_responses=True
            )
            cls._instance = redis.Redis(connection_pool=pool)
        return cls._instance

redis_client = RedisClient.get_instance()
