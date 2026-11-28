from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from pydantic import TypeAdapter

from api import utils
from api.kit.cache import CachedValue
from api.redis import Redis

pytestmark = pytest.mark.anyio


@pytest.fixture
async def cache(app: FastAPI) -> AsyncIterator[CachedValue[list[str]]]:
    redis = await app.state.dishka_container.get(Redis)
    value = CachedValue(redis, f"test:cache:{utils.common.unique_id()}", TypeAdapter(list[str]), ttl=30)
    yield value
    await redis.delete(value.key)


async def test_values_are_loaded_once(cache: CachedValue[list[str]]) -> None:
    load = AsyncMock(return_value=["a"])
    for _ in range(2):
        assert await cache.get(load) == ["a"]
    load.assert_called_once()
    assert 0 < await cache.redis.ttl(cache.key) <= 30


async def test_empty_values_are_cached(cache: CachedValue[list[str]]) -> None:
    load = AsyncMock(return_value=[])
    for _ in range(2):
        assert await cache.get(load) == []
    load.assert_called_once()


async def test_invalidated_values_are_loaded_again(cache: CachedValue[list[str]]) -> None:
    load = AsyncMock(side_effect=[["a"], ["b"]])
    assert await cache.get(load) == ["a"]
    await cache.invalidate()
    assert await cache.get(load) == ["b"]
    assert await cache.get(load) == ["b"]


async def test_values_loaded_during_an_invalidation_are_not_cached(cache: CachedValue[list[str]]) -> None:
    async def load_and_invalidate() -> list[str]:
        await cache.invalidate()
        return ["stale"]

    assert await cache.get(load_and_invalidate) == ["stale"]
    assert await cache.get(AsyncMock(return_value=["fresh"])) == ["fresh"]
