import os
import shutil

import pytest
from async_asgi_testclient import TestClient as AsyncClient
from dramatiq import Worker
from starlette.testclient import TestClient

from api import settings
from main import app


@pytest.yield_fixture(scope="session", autouse=True)
def event_loop():
    yield settings.loop


@pytest.yield_fixture(scope="session", autouse=True)
def client(event_loop):
    with TestClient(app) as client:
        yield client


@pytest.yield_fixture(scope="session")
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
    return client.post(
        "/token", json={"email": "testauth@example.com", "password": "test12345", "permissions": ["full_control"]},
    ).json()["access_token"]


@pytest.fixture(scope="session", autouse=True)
def stub_broker():
    settings.broker.flush_all()
    return settings.broker


@pytest.fixture(scope="session", autouse=True)
def stub_worker():
    worker = Worker(settings.broker, worker_timeout=100)
    worker.start()
    yield worker
    worker.stop()


@pytest.yield_fixture
def service_dir():
    directory = "test-1"
    os.mkdir(directory)
    with open(f"{directory}/hostname", "w") as f:
        f.write("test.onion\n\n\n")
    yield directory
    shutil.rmtree(directory)


@pytest.yield_fixture
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
