import pytest
from starlette.testclient import TestClient
from main import app


@pytest.yield_fixture(scope="session", autouse=True)
def client():
    with TestClient(app) as client:
        yield client
