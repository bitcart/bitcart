from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import pytest
from dishka import Scope
from fastapi import FastAPI

from api import utils
from api.services.crud.repositories.invoices import InvoiceRepository
from tests.helper import create_invoice, create_product, create_token, create_user

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

pytestmark = pytest.mark.anyio


async def test_multiple_query(client: TestClient, token: str) -> None:
    user1 = await create_user(client, token=token)
    user2 = await create_user(client, token=token)
    query = f"{user1['email']}|{user2['email']}"
    resp = await client.get(f"/users?multiple=true&query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


async def test_next_prev_url(client: TestClient, token: str) -> None:
    # create multiple users
    await create_user(client, token=token)
    await create_user(client, token=token)
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


async def test_undefined_sort(client: TestClient, token: str) -> None:
    resp = await client.get("/users?sort=fake", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["result"] == []


async def test_products_pagination(client: TestClient, token: str) -> None:
    product = await create_product(client, token)
    resp = await client.get(
        f"/products?store={product['store_id']}&category={product['category']}&           "
        f" min_price=0.001&max_price={product['price']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["count"] > 0


async def test_token_pagination(client: TestClient, user: dict[str, Any]) -> None:
    token_data = await create_token(client, user, app_id="998")
    permissions = ",".join(token_data["permissions"])
    resp = await client.get(
        f"/token?app_id={token_data['app_id']}&redirect_url={token_data['redirect_url']}&permissions={permissions}",
        headers={"Authorization": f"Bearer {token_data['id']}"},
    )
    assert resp.json()["count"] == 1


async def check_query(
    client: TestClient, token: str, column: str, value: Any, expected_count: int, allow_nonexisting: bool = False
) -> None:
    query = quote(f"{column}:{value}")
    resp = await client.get(f"/invoices?query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == expected_count
    if not allow_nonexisting:
        for item in resp.json()["result"]:
            assert item[column] == value


async def test_columns_queries(client: TestClient, token: str) -> None:
    await create_invoice(client, token, currency="USD")
    await create_invoice(client, token, currency="EUR")
    await check_query(client, token, "currency", "USD", 1)
    await check_query(client, token, "currency", "EUR", 1)


async def test_undefined_column_query(client: TestClient, token: str) -> None:
    await create_invoice(client, token, currency="test")
    await check_query(client, token, "test", "test", 1, allow_nonexisting=True)  # skips undefined columns


async def test_bad_type_column_query(client: TestClient, token: str) -> None:
    await create_invoice(client, token, price=10)
    await check_query(client, token, "price", "test", 0)


async def check_start_date_query(
    client: TestClient, token: str, date: str, expected_count: int, first_id: str, start: bool = True
) -> None:
    query = quote(f"start_date:{date}") if start else quote(f"end_date:{date}")
    ind = 0 if start else -1
    resp = await client.get(f"/invoices?query={query}&sort=created&desc=false", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == expected_count
    assert resp.json()["result"][ind]["id"] == first_id


async def test_date_pagination(client: TestClient, token: str, app: FastAPI) -> None:
    now = utils.time.now()
    invoice1 = await create_invoice(client, token)
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        invoice_repository = await container.get(InvoiceRepository)
        model = await invoice_repository.get_one(id=invoice1["id"])
        model.created = now - timedelta(hours=1)
    invoice2 = await create_invoice(client, token)
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        invoice_repository = await container.get(InvoiceRepository)
        model = await invoice_repository.get_one(id=invoice2["id"])
        model.created = now - timedelta(days=1)
    invoice3 = await create_invoice(client, token)
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        invoice_repository = await container.get(InvoiceRepository)
        model = await invoice_repository.get_one(id=invoice3["id"])
        model.created = now - timedelta(weeks=1)
    await check_start_date_query(client, token, "-2h", 1, invoice1["id"])
    await check_start_date_query(client, token, "-2d", 2, invoice2["id"])
    await check_start_date_query(client, token, "-2w", 3, invoice3["id"])
    await check_start_date_query(client, token, "-1w", 1, invoice3["id"], start=False)
    await check_start_date_query(client, token, "-1d", 2, invoice2["id"], start=False)
    await check_start_date_query(client, token, "-1h", 3, invoice1["id"], start=False)


async def test_autocomplete_response_format(client: TestClient, token: str) -> None:
    await create_user(client, token=token)
    resp = await client.get("/users?autocomplete=true", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 1
    for item in data["result"]:
        assert item.keys() == {"id", "name"}
    resp = await client.get("/users?autocomplete=false", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 1
    for item in data["result"]:
        assert item.keys() > {"id", "email", "is_superuser", "settings"}


async def check_metadata_query(client: TestClient, token: str, field: str, value: str, expected_count: int) -> None:
    query = quote(f"metadata.{field}:{value}")
    resp = await client.get(f"/invoices?query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == expected_count


async def test_metadata_query(client: TestClient, token: str, invoice: dict[str, Any], app: FastAPI) -> None:
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        invoice_repository = await container.get(InvoiceRepository)
        model = await invoice_repository.get_one(id=invoice["id"])
        model.meta = {"external_id": "abc123"}
    await check_metadata_query(client, token, "external_id", "abc123", 1)
    await check_metadata_query(client, token, "nonexistent", "value", 0)
    query = quote(f"metadata.external_id:abc123 status:{invoice['status']}")
    resp = await client.get(f"/invoices?query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1
