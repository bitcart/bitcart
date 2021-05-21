import pytest
from starlette.testclient import TestClient

from api import utils
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
def user(client: TestClient):
    data = {
        "email": f"superuser-{utils.common.unique_id()}@example.com",
        "is_superuser": True,
    }
    return create_user(client, **data)


@pytest.fixture(scope="class")
def token_data(client: TestClient, user):
    return create_token(client, user)


@pytest.fixture(scope="class")
def token(token_data):
    return token_data["access_token"]


@pytest.fixture(scope="class")
def limited_user(client: TestClient, user):
    data = {
        "email": f"nonsuperuser-{utils.common.unique_id()}@example.com",
        "is_superuser": False,
    }
    return create_user(client, **data)


@pytest.fixture(scope="class")
def limited_token(client: TestClient, limited_user):
    return create_token(client, limited_user, permissions=[])["access_token"]


@pytest.fixture(scope="class")
async def wallet(user):
    return await create_wallet(user["id"])


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
