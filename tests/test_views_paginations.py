import urllib.parse

from starlette.testclient import TestClient


def test_multiple_query(client: TestClient, token: str):
    user1 = "testauth@example.com"
    user2 = "test2auth@example.com"
    query = urllib.parse.quote(f"{user1}|{user2}")
    resp = client.get(f"/users?multiple=true&query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_next_prev_url(client: TestClient, token: str):
    # current url
    resp = client.get("/users?limit=1", headers={"Authorization": f"Bearer {token}"})
    next_url = resp.json()["next"]
    next_endpoint = next_url.split("testserver")[-1]
    assert next_endpoint == "/users?limit=1&offset=1"
    # previous
    resp = client.get(next_endpoint, headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    prev_endpoint = prev_url.split("testserver")[-1]
    assert prev_endpoint == "/users?limit=1"
    # next
    next_endpoint = resp.json()["next"].split("testserver")[-1]
    resp = client.get(next_endpoint, headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    prev_endpoint = prev_url.split("testserver")[-1]
    assert prev_endpoint == "/users?limit=1&offset=1"


def test_undefined_sort(client: TestClient, token: str):
    resp = client.get("/users?sort=fake", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["result"] == []


def test_products_pagination(client: TestClient, token: str):
    resp = client.get(
        "/products?store=2&category=Test&min_price=0.001&max_price=100.0", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.json()["count"] == 1


def test_token_pagination(client: TestClient, token: str):
    resp = client.get(
        "/token?app_id=1&redirect_url=google.com:443&permissions=full_control", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.json()["count"] == 1
