import pytest
from starlette.testclient import TestClient

from main import app


@pytest.yield_fixture(scope="session", autouse=True)
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def token(client):
    client.post("/users", json={"username": "testauth", "password": "test12345"})
    return client.post(
        "/token", json={"username": "testauth", "password": "test12345"}
    ).json()["access_token"]
