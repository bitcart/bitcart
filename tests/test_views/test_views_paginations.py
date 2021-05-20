import pytest
from starlette.testclient import TestClient

from tests.helper import create_product, create_token, create_user


@pytest.mark.asyncio
async def test_multiple_query(async_client, token: str):
    user1 = await create_user()
    user2 = await create_user()
    query = f"{user1.email}|{user2.email}"
    resp = await async_client.get(f"/users?multiple=true&query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_next_prev_url(async_client, token: str):
    # creat multiple users
    await create_user()
    await create_user()
    resp = await async_client.get("/users?limit=1", headers={"Authorization": f"Bearer {token}"})
    next_url = resp.json()["next"]
    assert next_url.endswith("/users?limit=1&offset=1")
    # previous
    resp = await async_client.get("/users?limit=1&offset=1", headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    assert prev_url.endswith("/users?limit=1")
    # next
    resp = await async_client.get("/users?limit=1&offset=2", headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    assert prev_url.endswith("/users?limit=1&offset=1")


def test_undefined_sort(client: TestClient, token: str):
    resp = client.get("/users?sort=fake", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["result"] == []


@pytest.mark.asyncio
async def test_products_pagination(async_client, user, token: str):
    product_obj = await create_product(user.id)
    resp = await async_client.get(
        f"/products?store={product_obj.store_id}&category={product_obj.category}&\
            min_price=0.001&max_price={product_obj.price}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["count"] > 0


@pytest.mark.asyncio
async def test_token_pagination(async_client, user):
    token_obj = await create_token(user.id, app_id="998")
    permissions = ",".join(token_obj.permissions)
    resp = await async_client.get(
        f"/token?app_id={token_obj.app_id}&redirect_url={token_obj.redirect_url}&permissions={permissions}",
        headers={"Authorization": f"Bearer {token_obj.id}"},
    )
    assert resp.json()["count"] == 1
