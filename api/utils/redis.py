import asyncio
import json
from contextlib import asynccontextmanager

from redis.asyncio.client import PubSub

from api import settings, utils


@asynccontextmanager
async def wait_for_redis():  # pragma: no cover
    while not settings.settings.redis_pool:
        await asyncio.sleep(0.01)
    yield


class MyPubSub(PubSub):  # see https://github.com/redis/redis-py/issues/2912
    async def execute_command(self, *args, **options):
        return await asyncio.shield(super().execute_command(*args, **options))


async def make_subscriber(name):
    async with wait_for_redis():
        subscriber = MyPubSub(settings.settings.redis_pool.connection_pool, ignore_subscribe_messages=True)
        await subscriber.subscribe(f"channel:{name}")
        return subscriber


async def publish_message(channel, message):
    async with wait_for_redis():
        return await settings.settings.redis_pool.publish(f"channel:{channel}", json.dumps(message))


async def listen_channel(channel):
    async for message in channel.listen():
        yield json.loads(message["data"])


async def wait_for_task_result(task_id):
    async with wait_for_redis():
        while True:
            result = await settings.settings.redis_pool.get(f"task:{task_id}")
            if result:
                await settings.settings.redis_pool.delete(f"task:{task_id}")
                return json.loads(result, object_hook=utils.common.decimal_aware_object_hook)
            await asyncio.sleep(0.01)


async def set_task_result(task_id, result):  # pragma: no cover
    async with wait_for_redis():
        return await settings.settings.redis_pool.set(
            f"task:{task_id}", json.dumps(result, cls=utils.common.DecimalAwareJSONEncoder)
        )
