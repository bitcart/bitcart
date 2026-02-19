from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
def notification_template() -> str:
    with open("api/templates/notification.j2") as f:
        return f.read().strip()


@pytest.fixture
async def user(client: TestClient, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_user(client, **cast(dict[str, Any], static_data.SUPER_USER_DATA))


@pytest.fixture
async def token_data(client: TestClient, user: dict[str, Any], anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_token(client, user)


@pytest.fixture
def token(token_data: dict[str, Any]) -> str:
    return token_data["access_token"]


@pytest.fixture
async def limited_user(client: TestClient, token: str, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    data = {
        "email": f"nonsuperuser-{utils.common.unique_id()}@example.com",
        "is_superuser": False,
    }
    return await create_user(client, token=token, **data)


@pytest.fixture
async def limited_token(client: TestClient, limited_user: dict[str, Any], anyio_backend: tuple[str, dict[str, Any]]) -> str:
    return (await create_token(client, limited_user, permissions=[]))["access_token"]


@pytest.fixture
async def wallet(client: TestClient, anyio_backend: tuple[str, dict[str, Any]], token: str) -> dict[str, Any]:
    return await create_wallet(client, token)


@pytest.fixture
async def store(client: TestClient, token: str, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_store(client, token)


@pytest.fixture
async def discount(client: TestClient, token: str, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_discount(client, token)


@pytest.fixture
async def product(client: TestClient, token: str, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_product(client, token)


@pytest.fixture
async def invoice(client: TestClient, token: str, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_invoice(client, token)


@pytest.fixture
async def notification(client: TestClient, token: str, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_notification(client, token)


@pytest.fixture
def image() -> bytes:
    with open("tests/fixtures/img/image.png", "rb") as f:
        return f.read()
