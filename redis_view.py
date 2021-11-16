import redis
from luracoin.config import Config

redis_client = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    db=Config.REDIS_DB,
)

key = "7e3b18751c35898b2728f3402391acd208b06adde000b1926730173e9a95e159"

result = redis_client.get(key)
print(result.hex())
print(redis_client.keys())