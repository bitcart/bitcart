import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Any

import redis
from fastapi import HTTPException
from redis.asyncio.client import PubSub

from api.redis import Redis


# TODO: when integrating fakeredis, remove this
class MyPubSub(PubSub):  # see https://github.com/redis/redis-py/issues/2912
    async def execute_command(self, *args: Any, **options: Any) -> Any:
        return await asyncio.shield(super().execute_command(*args, **options))


async def make_subscriber(redis_pool: Redis, name: str) -> MyPubSub:
    subscriber = MyPubSub(redis_pool.connection_pool, ignore_subscribe_messages=True)
    await subscriber.subscribe(f"channel:{name}")
    return subscriber


async def publish_message(redis_pool: Redis, channel: str, message: Any) -> int:
    return await redis_pool.publish(f"channel:{channel}", json.dumps(message))


async def check_rate_limit(redis_pool: Redis, rate_key: str, max_attempts: int, window: int, error_message: str) -> None:
    attempts = await redis_pool.incr(rate_key)
    if attempts == 1:
        await redis_pool.expire(rate_key, window)
    if attempts > max_attempts:
        raise HTTPException(429, error_message)


async def listen_channel(channel: MyPubSub) -> AsyncIterator[Any]:
    try:
        async for message in channel.listen():
            with contextlib.suppress(Exception):
                yield json.loads(message["data"])
    except redis.exceptions.ConnectionError:  # pragma: no cover
        pass
