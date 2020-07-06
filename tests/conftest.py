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
def client():
    with TestClient(app) as client:
        yield client


@pytest.yield_fixture(scope="session")
async def async_client():
    async with AsyncClient(app) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def notification_template():
    with open("api/templates/notification.j2") as f:
        text = f.read()
    return text


@pytest.fixture(scope="session", autouse=True)
def token(client):
    client.post(
        "/users", json={"email": "testauth@example.com", "password": "test12345"}
    )
    return client.post(
        "/token",
        json={
            "email": "testauth@example.com",
            "password": "test12345",
            "permissions": ["full_control"],
        },
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
