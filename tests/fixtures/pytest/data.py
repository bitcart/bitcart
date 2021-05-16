from uuid import uuid4

import pytest

from tests.helper import (
    create_discount,
    create_notification,
    create_product,
    create_store,
    create_store_wallet,
    create_token,
    create_user,
    create_wallet,
)


@pytest.fixture(scope="session", autouse=True)
def notification_template():
    with open("api/templates/notification.j2") as f:
        text = f.read()
    return text


@pytest.fixture(scope="class")
async def user():
    data = {
        "email": f"superuser-{uuid4().hex[:8]}@example.com",
        "password": "test12345",
        "is_superuser": True,
    }
    user_obj = await create_user(**data)
    return {**user_obj.to_dict(), **data}


@pytest.fixture(scope="class")
async def token_obj(user):
    return await create_token(user["id"])


@pytest.fixture(scope="class")
async def token(token_obj):
    return token_obj.id


@pytest.fixture(scope="class")
async def wallet(user):
    return await create_wallet(user["id"])


@pytest.fixture(scope="class")
async def limited_user():
    data = {
        "email": f"nonsuperuser-{uuid4().hex[:8]}@example.com",
        "password": "test12345",
        "is_superuser": False,
    }
    user_obj = await create_user(**data)
    return {**user_obj.to_dict(), **data}


@pytest.fixture(scope="class")
async def limited_token(limited_user):
    return (await create_token(limited_user["id"], permissions=[])).id


@pytest.fixture(scope="class")
async def store(user):
    return await create_store(user["id"])


@pytest.fixture(scope="class")
async def store_wallet(user):
    return await create_store_wallet(user["id"])


@pytest.fixture(scope="class")
async def discount(user):
    return await create_discount(user["id"])


@pytest.fixture(scope="class")
async def product(user):
    return await create_product(user["id"])


@pytest.fixture(scope="class")
async def notification(user):
    return await create_notification(user["id"])


@pytest.fixture
def image():
    with open("tests/fixtures/img/image.png", "rb") as f:
        data = f.read()
    return data
