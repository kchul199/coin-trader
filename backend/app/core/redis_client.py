import redis.asyncio as redis
from typing import Optional

from app.config import settings

_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """
    Get or create an async Redis connection.

    Returns:
        Redis async client instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = await redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
