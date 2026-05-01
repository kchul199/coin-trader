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
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client:
        close = getattr(_redis_client, "aclose", None)
        if close is not None:
            await close()
        else:
            await _redis_client.close()
        _redis_client = None
