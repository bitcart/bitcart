from starlette.testclient import TestClient

from main import app

client = TestClient(app)


def test_no_root():
    response = client.get("/")
    assert response.status_code == 404
