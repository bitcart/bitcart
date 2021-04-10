import pytest

from api import crud

pytestmark = pytest.mark.asyncio


async def test_store_add_related_non_store():
    assert await crud.stores.store_add_related(None) is None


async def test_product_add_related_non_product():
    assert await crud.products.product_add_related(None) is None
