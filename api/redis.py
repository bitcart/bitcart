from collections.abc import AsyncIterator
from typing import cast

import redis.asyncio as _async_redis
from fastapi import Request
from redis import ConnectionError as RedisConnectionError
from redis import RedisError
from redis import TimeoutError as RedisTimeoutError
from redis.asyncio.client import PubSub
from redis.asyncio.retry import Retry
from redis.backoff import default_backoff

from api.settings import Settings

Redis = _async_redis.Redis


REDIS_RETRY_ON_ERRROR: list[type[RedisError]] = [RedisConnectionError, RedisTimeoutError]
REDIS_RETRY = Retry(default_backoff(), retries=50)


async def create_redis(settings: Settings) -> AsyncIterator[Redis]:
    redis = cast(
        Redis,
        _async_redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            retry_on_error=REDIS_RETRY_ON_ERRROR,
            retry=REDIS_RETRY,
        ),
    )
    yield redis
    await redis.close()


async def get_redis(request: Request) -> Redis:
    return request.state.redis


__all__ = [
    "Redis",
    "PubSub",
    "REDIS_RETRY_ON_ERRROR",
    "REDIS_RETRY",
    "create_redis",
    "get_redis",
]
