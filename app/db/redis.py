from redis.asyncio import from_url
from app.core.config import settings

redis_client = from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)

async def get_redis():
    return redis_client
