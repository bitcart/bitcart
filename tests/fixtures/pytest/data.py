from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from api import utils
from tests.fixtures import static_data
from tests.helper import (
    create_discount,
    create_invoice,
    create_notification,
    create_product,
    create_store,
    create_token,
    create_user,
    create_wallet,
)

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient


@pytest.fixture(scope="session", autouse=True)
def notification_template():
    with open("api/templates/notification.j2") as f:
        text = f.read().strip()
    return text


@pytest.fixture
async def user(client: TestClient, anyio_backend):
    return await create_user(client, **static_data.SUPER_USER_DATA)


@pytest.fixture
async def token_data(client: TestClient, user, anyio_backend):
    return await create_token(client, user)


@pytest.fixture
def token(token_data):
    return token_data["access_token"]


@pytest.fixture
async def limited_user(client: TestClient, user, anyio_backend):
    data = {
        "email": f"nonsuperuser-{utils.common.unique_id()}@example.com",
        "is_superuser": False,
    }
    return await create_user(client, **data)


@pytest.fixture
async def limited_token(client: TestClient, limited_user, anyio_backend):
    return (await create_token(client, limited_user, permissions=[]))["access_token"]


@pytest.fixture
async def wallet(client: TestClient, user, token, anyio_backend):
    return await create_wallet(client, user["id"], token)


@pytest.fixture
async def store(client: TestClient, user, token, anyio_backend):
    return await create_store(client, user["id"], token)


@pytest.fixture
async def discount(client: TestClient, user, token, anyio_backend):
    return await create_discount(client, user["id"], token)


@pytest.fixture
async def product(client: TestClient, user, token, anyio_backend):
    return await create_product(client, user["id"], token)


@pytest.fixture
async def invoice(client: TestClient, user, token, anyio_backend):
    return await create_invoice(client, user["id"], token)


@pytest.fixture
async def notification(client: TestClient, user, token, anyio_backend):
    return await create_notification(client, user["id"], token)


@pytest.fixture
def image():
    with open("tests/fixtures/img/image.png", "rb") as f:
        data = f.read()
    return data
