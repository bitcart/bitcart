import pytest

from api import crud

pytestmark = pytest.mark.asyncio


async def test_store_add_related_non_store():
    assert await crud.store_add_related(None) is None


async def test_product_add_related_non_product():
    assert await crud.product_add_related(None) is None
