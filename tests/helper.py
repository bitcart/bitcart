from __future__ import annotations

import json as json_module
import random
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from api import utils
from api.settings import Settings
from tests.fixtures import static_data

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient


async def create_user(client: TestClient, *, token: str | None = None, **custom_attrs: Any) -> dict[str, Any]:
    default_attrs = {
        "email": f"user_{utils.common.unique_id()}@gmail.com",
        "password": static_data.USER_PWD,
        "is_superuser": True,
    }
    user = await create_model_obj(client, "users", default_attrs, custom_attrs, token=token)
    token = user.pop("token")
    await client.delete(f"/token/{token}", headers={"Authorization": f"Bearer {token}"})
    return user


async def create_token(client: TestClient, user: dict[str, Any], **custom_attrs: Any) -> dict[str, Any]:
    default_attrs = {
        "email": user["email"],
        "password": static_data.USER_PWD,
        "permissions": ["full_control"],
    }
    return await create_model_obj(client, "token", default_attrs, custom_attrs)


async def create_invoice(client: TestClient, token: str, **custom_attrs: Any) -> dict[str, Any]:
    store_id = custom_attrs.pop("store_id") if "store_id" in custom_attrs else (await create_store(client, token))["id"]
    default_attrs = {
        "price": random.randint(1, 10),
        "store_id": store_id,
    }
    return await create_model_obj(client, "invoices", default_attrs, custom_attrs, token=token)


async def create_product(client: TestClient, token: str, **custom_attrs: Any) -> dict[str, Any]:
    name = f"dummy_{utils.common.unique_id()}"
    store_id = custom_attrs.pop("store_id") if "store_id" in custom_attrs else (await create_store(client, token))["id"]
    default_attrs = {
        "name": name,
        "price": random.randint(1, 10),
        "quantity": random.randint(100, 200),
        "store_id": store_id,
    }
    return await create_model_obj(client, "products", default_attrs, custom_attrs, token=token)


async def create_wallet(client: TestClient, token: str, **custom_attrs: Any) -> dict[str, Any]:
    name = f"dummy_wallet_{utils.common.unique_id()}"
    default_attrs = {
        "name": name,
        "xpub": static_data.TEST_XPUB,
    }
    return await create_model_obj(client, "wallets", default_attrs, custom_attrs, token=token)


async def create_store(
    client: TestClient,
    token: str,
    custom_store_attrs: dict[str, Any] | None = None,
    custom_wallet_attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if custom_wallet_attrs is None:
        custom_wallet_attrs = {}
    if custom_store_attrs is None:
        custom_store_attrs = {}
    wallet = await create_wallet(client, token, **custom_wallet_attrs)
    name = f"dummy_store_{utils.common.unique_id()}"
    default_attrs = {
        "name": name,
        "wallets": [wallet["id"]],
    }
    return await create_model_obj(client, "stores", default_attrs, custom_store_attrs, token=token)


async def create_discount(client: TestClient, token: str, **custom_attrs: Any) -> dict[str, Any]:
    name = f"dummy_discount_{utils.common.unique_id()}"
    end_date = utils.time.now() + timedelta(days=1)
    default_attrs = {
        "name": name,
        "percent": 5,
        "promocode": "TEST",
        "end_date": end_date.isoformat(),
    }
    return await create_model_obj(client, "discounts", default_attrs, custom_attrs, token=token)


async def create_notification(client: TestClient, token: str, **custom_attrs: Any) -> dict[str, Any]:
    name = f"dummy_notf_{utils.common.unique_id()}"
    default_attrs = {
        "name": name,
        "provider": "Telegram",
        "data": {},
    }
    return await create_model_obj(client, "notifications", default_attrs, custom_attrs, token=token)


async def create_payout(
    client: TestClient,
    token: str,
    custom_payout_attrs: dict[str, Any] | None = None,
    custom_store_attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if custom_store_attrs is None:
        custom_store_attrs = {}
    if custom_payout_attrs is None:
        custom_payout_attrs = {}
    store = await create_store(client, token, **custom_store_attrs)
    default_attrs = {
        "amount": 5,
        "destination": static_data.PAYOUT_DESTINATION,
        "store_id": store["id"],
        "wallet_id": store["wallets"][0],
    }
    return await create_model_obj(client, "payouts", default_attrs, custom_payout_attrs, token=token)


async def create_model_obj(
    client: TestClient,
    endpoint: str,
    default_attrs: dict[str, Any],
    custom_attrs: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    if custom_attrs is None:
        custom_attrs = {}
    attrs = {**default_attrs, **custom_attrs}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if endpoint in static_data.FILE_UPLOAD_ENDPOINTS:
        resp = await client.post(endpoint, data={"data": json_module.dumps(attrs)}, headers=headers)
    else:
        resp = await client.post(endpoint, json=attrs, headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


@contextmanager
def enabled_logs(settings: Settings, datadir: str | None = None) -> Iterator[None]:
    old_datadir = settings.DATADIR
    settings.DATADIR = datadir or "tests/fixtures"
    settings.LOG_FILE_NAME = "bitcart.log"
    yield
    settings.DATADIR = old_datadir
    settings.LOG_FILE_NAME = None
