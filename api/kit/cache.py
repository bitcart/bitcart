import contextlib
from collections.abc import Awaitable, Callable

from pydantic import TypeAdapter
from redis.asyncio import Redis
from redis.exceptions import WatchError


class CachedValue[T]:
    """Redis copy of a value whose source of truth is elsewhere, usually the database.

    invalidate() must run after the change to the source is committed.
    """

    def __init__(self, redis: Redis, key: str, adapter: TypeAdapter[T], ttl: int) -> None:
        self.redis = redis
        self.key = key
        self.adapter = adapter
        self.ttl = ttl

    async def get(self, load: Callable[[], Awaitable[T]]) -> T:
        if cached := await self.redis.get(self.key):
            return self.adapter.validate_json(cached)
        async with self.redis.pipeline() as pipe:
            await pipe.watch(self.key)
            value = await load()
            pipe.multi()
            pipe.set(self.key, self.adapter.dump_json(value), ex=self.ttl)
            with contextlib.suppress(WatchError):
                await pipe.execute()
        return value

    async def invalidate(self) -> None:
        await self.redis.set(self.key, "", ex=self.ttl)
