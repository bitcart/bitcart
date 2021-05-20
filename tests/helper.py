import random
from datetime import datetime

from api import models, utils
from tests.fixtures import static_data


async def create_user(**custom_attrs) -> models.User:
    default_attrs = {
        "email": f"user_{utils.common.unique_id()}@gmail.com",
        "password": "test12345",
        "is_superuser": True,
        "created": utils.time.now(),
    }
    attrs = {**default_attrs, **custom_attrs}
    attrs["hashed_password"] = utils.authorization.get_password_hash(attrs.pop("password"))
    return await create_model_obj(models.User, attrs)


async def create_token(user_id: int, **custom_attrs) -> models.Token:
    token_id = utils.common.unique_id()
    default_attrs = {
        "id": token_id,
        "user_id": user_id,
        "app_id": "1",
        "redirect_url": "test.com",
        "permissions": ["full_control"],
        "created": utils.time.now(),
    }
    return await create_model_obj(models.Token, default_attrs, custom_attrs)


async def create_invoice(user_id: int, **custom_attrs) -> models.Invoice:
    if "store_id" in custom_attrs:
        store_id = custom_attrs.pop("store_id")
    else:
        store_id = (await create_store(user_id)).id
    default_attrs = {
        "price": random.randint(1, 10),
        "currency": "USD",
        "paid_currency": "BTC",
        "status": "complete",
        "expiration": 15,
        "buyer_email": "dummy_invoice@example.com",
        "store_id": store_id,
        "user_id": user_id,
        "created": utils.time.now(),
    }
    return await create_model_obj(models.Invoice, default_attrs, custom_attrs)


async def create_product(user_id: int, **custom_attrs) -> models.Product:
    name = f"dummy_{utils.common.unique_id()}"
    if "store_id" in custom_attrs:
        store_id = custom_attrs.pop("store_id")
    else:
        store_id = (await create_store(user_id)).id
    default_attrs = {
        "name": name,
        "price": random.randint(1, 10),
        "quantity": random.randint(100, 200),
        "download_url": f"{name}.com",
        "category": "general",
        "description": "description",
        "image": "",
        "store_id": store_id,
        "status": "active",
        "user_id": user_id,
        "created": datetime.now(),
    }
    return await create_model_obj(models.Product, default_attrs, custom_attrs)


async def create_store(user_id: int, **custom_attrs) -> models.Store:
    name = f"dummy_store_{utils.common.unique_id()}"
    default_attrs = {
        "name": name,
        "default_currency": "USD",
        "email": f"{name}@gmail.com",
        "email_host": "google.com",
        "email_password": "test12345",
        "email_port": 433,
        "email_user": name,
        "email_use_ssl": False,
        "user_id": user_id,
        "created": datetime.now(),
    }
    return await create_model_obj(models.Store, default_attrs, custom_attrs)


async def create_wallet(user_id: int, **custom_attrs) -> models.Wallet:
    name = f"dummy_wallet_{utils.common.unique_id()}"
    default_attrs = {
        "name": name,
        "xpub": static_data.TEST_XPUB,
        "currency": "btc",
        "user_id": user_id,
        "created": datetime.now(),
    }
    return await create_model_obj(models.Wallet, default_attrs, custom_attrs)


async def create_store_wallet(user_id: int, custom_store_attrs: dict = {}, custom_wallet_attrs: dict = {}) -> dict:
    store_obj = await create_store(user_id, **custom_store_attrs)
    wallet_obj = await create_wallet(user_id, **custom_wallet_attrs)
    await models.WalletxStore.create(wallet_id=wallet_obj.id, store_id=store_obj.id)
    return {"store": store_obj, "wallet": wallet_obj}


async def create_discount(user_id: int, **custom_attrs) -> models.Discount:
    name = f"dummy_discount_{utils.common.unique_id()}"
    default_attrs = {
        "user_id": user_id,
        "name": name,
        "percent": 5,
        "description": "",
        "promocode": "TEST",
        "currencies": "",
        "end_date": datetime.now(),
        "created": datetime.now(),
    }
    return await create_model_obj(models.Discount, default_attrs, custom_attrs)


async def create_notification(user_id: int, **custom_attrs) -> models.Notification:
    name = f"dummy_notf_{utils.common.unique_id()}"
    default_attrs = {
        "user_id": user_id,
        "name": name,
        "provider": "NA",
        "data": {},
        "created": datetime.now(),
    }
    return await create_model_obj(models.Notification, default_attrs, custom_attrs)


async def create_model_obj(model_cls, default_attrs, custom_attrs={}):
    attrs = {**default_attrs, **custom_attrs}
    return await model_cls.create(**attrs)
