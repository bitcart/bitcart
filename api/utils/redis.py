import asyncio

import aioredis

from .. import settings


class WaitForRedis:  # pragma: no cover
    async def __aenter__(self):
        while not settings.redis_pool:
            await asyncio.sleep(0.01)

    async def __aexit__(self, exc_type, exc, tb):
        pass


wait_for_redis = WaitForRedis


async def make_subscriber(name):
    subscriber = await aioredis.create_redis_pool(settings.REDIS_HOST)
    res = await subscriber.subscribe(f"channel:{name}")
    channel = res[0]
    return subscriber, channel


async def publish_message(channel, message):
    async with wait_for_redis():
        return await settings.redis_pool.publish_json(f"channel:{channel}", message)
