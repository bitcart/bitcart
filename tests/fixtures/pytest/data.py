import pytest
from starlette.testclient import TestClient

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


@pytest.fixture(scope="session", autouse=True)
def notification_template():
    with open("api/templates/notification.j2") as f:
        text = f.read()
    return text


@pytest.fixture(scope="class")
def user(client: TestClient):
    return create_user(client, **static_data.SUPER_USER_DATA)


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
def wallet(client: TestClient, user, token):
    return create_wallet(client, user["id"], token)


@pytest.fixture(scope="class")
def store(client: TestClient, user, token):
    return create_store(client, user["id"], token)


@pytest.fixture(scope="class")
def discount(client: TestClient, user, token):
    return create_discount(client, user["id"], token)


@pytest.fixture(scope="class")
def product(client: TestClient, user, token):
    return create_product(client, user["id"], token)


@pytest.fixture(scope="class")
def invoice(client: TestClient, user, token):
    return create_invoice(client, user["id"], token)


@pytest.fixture(scope="class")
def notification(client: TestClient, user, token):
    return create_notification(client, user["id"], token)


@pytest.fixture
def image():
    with open("tests/fixtures/img/image.png", "rb") as f:
        data = f.read()
    return data
