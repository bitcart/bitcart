import os
import shutil

import pytest
from async_asgi_testclient import TestClient as AsyncClient
from starlette.testclient import TestClient

from api import settings
from main import app


@pytest.fixture(scope="session", autouse=True)
def event_loop():
    yield settings.loop


@pytest.fixture(scope="session", autouse=True)
def client(event_loop):
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
async def async_client(event_loop):
    async with AsyncClient(app) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def notification_template():
    with open("api/templates/notification.j2") as f:
        text = f.read()
    return text


@pytest.fixture(scope="session", autouse=True)
def token(client):
    client.post("/users", json={"email": "testauth@example.com", "password": "test12345"})
    v = client.post(
        "/token",
        json={
            "email": "testauth@example.com",
            "password": "test12345",
            "app_id": "1",
            "redirect_url": "test.com",
            "permissions": ["full_control"],
        },
    )
    print(v.status_code, v.text)
    return v.json()["access_token"]


@pytest.fixture
def service_dir():
    directory = "test-1"
    os.mkdir(directory)
    with open(f"{directory}/hostname", "w") as f:
        f.write("test.onion\n\n\n")
    yield directory
    shutil.rmtree(directory)


@pytest.fixture
def torrc(service_dir):
    filename = "torrc"
    with open(filename, "w") as f:
        f.write(
            """
HiddenServiceDir test-1
HiddenServicePort 80 127.0.0.1:80"""
        )
    yield filename
    os.remove(filename)


@pytest.fixture
def image():
    with open("tests/fixtures/image.png", "rb") as f:
        data = f.read()
    return data


def deleting_file_base(filename):
    assert os.path.exists(filename)
    with open(filename) as f:
        contents = f.read()
    yield filename
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write(contents)


@pytest.fixture
def log_file():
    yield from deleting_file_base("tests/fixtures/bitcart.log")


@pytest.fixture
def log_file_deleting():
    yield from deleting_file_base("tests/fixtures/bitcart-log.log.test")
