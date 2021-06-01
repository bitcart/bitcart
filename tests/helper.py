import json as json_module
import random
from datetime import timedelta

from starlette.testclient import TestClient

from api import utils
from tests.fixtures import static_data


def create_user(client: TestClient, **custom_attrs) -> dict:
    default_attrs = {
        "email": f"user_{utils.common.unique_id()}@gmail.com",
        "password": static_data.USER_PWD,
        "is_superuser": True,
    }
    return create_model_obj(client, "users", default_attrs, custom_attrs)


def create_token(client, user: dict, **custom_attrs) -> dict:
    default_attrs = {
        "email": user["email"],
        "password": static_data.USER_PWD,
        "permissions": ["full_control"],
    }
    return create_model_obj(client, "token", default_attrs, custom_attrs)


def create_invoice(client, user_id: str, token: str, **custom_attrs) -> dict:
    if "store_id" in custom_attrs:
        store_id = custom_attrs.pop("store_id")
    else:
        store_id = create_store(client, user_id, token)["id"]
    default_attrs = {
        "price": random.randint(1, 10),
        "store_id": store_id,
        "user_id": user_id,
    }
    return create_model_obj(client, "invoices", default_attrs, custom_attrs, token=token)


def create_product(client, user_id: str, token: str, **custom_attrs) -> dict:
    name = f"dummy_{utils.common.unique_id()}"
    if "store_id" in custom_attrs:
        store_id = custom_attrs.pop("store_id")
    else:
        store_id = create_store(client, user_id, token)["id"]
    default_attrs = {
        "name": name,
        "price": random.randint(1, 10),
        "quantity": random.randint(100, 200),
        "store_id": store_id,
        "user_id": user_id,
    }
    return create_model_obj(client, "products", default_attrs, custom_attrs, token=token)


def create_wallet(client, user_id: str, token: str, **custom_attrs) -> dict:
    name = f"dummy_wallet_{utils.common.unique_id()}"
    default_attrs = {
        "name": name,
        "xpub": static_data.TEST_XPUB,
        "user_id": user_id,
    }
    return create_model_obj(client, "wallets", default_attrs, custom_attrs, token=token)


def create_store(client, user_id: str, token: str, custom_store_attrs: dict = {}, custom_wallet_attrs: dict = {}) -> dict:
    wallet = create_wallet(client, user_id, token, **custom_wallet_attrs)
    name = f"dummy_store_{utils.common.unique_id()}"
    default_attrs = {
        "name": name,
        "wallets": [wallet["id"]],
        "user_id": user_id,
    }
    return create_model_obj(client, "stores", default_attrs, custom_store_attrs, token=token)


def create_discount(client, user_id: str, token: str, **custom_attrs) -> dict:
    name = f"dummy_discount_{utils.common.unique_id()}"
    end_date = utils.time.now() + timedelta(days=1)
    default_attrs = {
        "user_id": user_id,
        "name": name,
        "percent": 5,
        "promocode": "TEST",
        "end_date": end_date.isoformat(),
    }
    return create_model_obj(client, "discounts", default_attrs, custom_attrs, token=token)


def create_notification(client, user_id: str, token: str, **custom_attrs) -> dict:
    name = f"dummy_notf_{utils.common.unique_id()}"
    default_attrs = {
        "user_id": user_id,
        "name": name,
        "provider": "telegram",
        "data": {},
    }
    return create_model_obj(client, "notifications", default_attrs, custom_attrs, token=token)


def create_model_obj(client, endpoint, default_attrs, custom_attrs={}, token: str = None):
    attrs = {**default_attrs, **custom_attrs}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    if endpoint in static_data.FILE_UPLOAD_ENDPOINTS:
        resp = client.post(endpoint, data={"data": json_module.dumps(attrs)}, headers=headers)
    else:
        resp = client.post(endpoint, json=attrs, headers=headers)
    assert resp.status_code == 200
    return resp.json()
