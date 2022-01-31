from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote

import pytest

from api import utils
from tests.helper import create_invoice, create_product, create_token, create_user

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

pytestmark = pytest.mark.anyio


async def test_multiple_query(client: TestClient, token: str):
    user1 = await create_user(client)
    user2 = await create_user(client)
    query = f"{user1['email']}|{user2['email']}"
    resp = await client.get(f"/users?multiple=true&query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


async def test_next_prev_url(client: TestClient, token: str):
    # create multiple users
    await create_user(client)
    await create_user(client)
    resp = await client.get("/users?limit=1", headers={"Authorization": f"Bearer {token}"})
    next_url = resp.json()["next"]
    assert next_url.endswith("/users?limit=1&offset=1")
    # previous
    resp = await client.get("/users?limit=1&offset=1", headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    assert prev_url.endswith("/users?limit=1")
    # next
    resp = await client.get("/users?limit=1&offset=2", headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    assert prev_url.endswith("/users?limit=1&offset=1")


async def test_undefined_sort(client: TestClient, token: str):
    resp = await client.get("/users?sort=fake", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["result"] == []


async def test_products_pagination(client: TestClient, user, token: str):
    product = await create_product(client, user["id"], token)
    resp = await client.get(
        f"/products?store={product['store_id']}&category={product['category']}&           "
        f" min_price=0.001&max_price={product['price']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["count"] > 0


async def test_token_pagination(client: TestClient, user):
    token_data = await create_token(client, user, app_id="998")
    permissions = ",".join(token_data["permissions"])
    resp = await client.get(
        f"/token?app_id={token_data['app_id']}&redirect_url={token_data['redirect_url']}&permissions={permissions}",
        headers={"Authorization": f"Bearer {token_data['id']}"},
    )
    assert resp.json()["count"] == 1


async def check_query(client: TestClient, token: str, column, value, expected_count, allow_nonexisting=False):
    query = quote(f"{column}:{value}")
    resp = await client.get(f"/invoices?query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == expected_count
    if not allow_nonexisting:
        for item in resp.json()["result"]:
            assert item[column] == value


async def test_columns_queries(client: TestClient, user, token):
    await create_invoice(client, user["id"], token, currency="USD")
    await create_invoice(client, user["id"], token, currency="EUR")
    await check_query(client, token, "currency", "USD", 1)
    await check_query(client, token, "currency", "EUR", 1)


async def test_undefined_column_query(client: TestClient, user, token):
    await create_invoice(client, user["id"], token, currency="test")
    await check_query(client, token, "test", "test", 1, allow_nonexisting=True)  # skips undefined columns


async def test_bad_type_column_query(client: TestClient, user, token):
    await create_invoice(client, user["id"], token, price=10)
    await check_query(client, token, "price", "test", 0)


async def check_start_date_query(client, token, date, expected_count, first_id, start=True):
    query = quote(f"start_date:{date}") if start else quote(f"end_date:{date}")
    ind = 0 if start else -1
    resp = await client.get(f"/invoices?query={query}&sort=created&desc=false", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == expected_count
    assert resp.json()["result"][ind]["id"] == first_id


async def test_date_pagination(client: TestClient, user, token):
    now = utils.time.now()
    invoice1 = await create_invoice(client, user["id"], token, created=(now - timedelta(hours=1)).isoformat())
    invoice2 = await create_invoice(client, user["id"], token, created=(now - timedelta(days=1)).isoformat())
    invoice3 = await create_invoice(client, user["id"], token, created=(now - timedelta(weeks=1)).isoformat())
    await check_start_date_query(client, token, "-2h", 1, invoice1["id"])
    await check_start_date_query(client, token, "-2d", 2, invoice2["id"])
    await check_start_date_query(client, token, "-2w", 3, invoice3["id"])
    await check_start_date_query(client, token, "-1w", 1, invoice3["id"], start=False)
    await check_start_date_query(client, token, "-1d", 2, invoice2["id"], start=False)
    await check_start_date_query(client, token, "-1h", 3, invoice1["id"], start=False)
