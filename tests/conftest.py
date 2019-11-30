import pytest
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


@pytest.fixture(scope="session", autouse=True)
def token(client):
    client.post(
        "/users", json={"email": "testauth@example.com", "password": "test12345"}
    )
    return client.post(
        "/token", json={"email": "testauth@example.com", "password": "test12345"}
    ).json()["access_token"]
