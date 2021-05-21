from starlette.testclient import TestClient

from tests.helper import create_product, create_token, create_user


def test_multiple_query(client: TestClient, token: str):
    user1 = create_user(client)
    user2 = create_user(client)
    query = f"{user1['email']}|{user2['email']}"
    resp = client.get(f"/users?multiple=true&query={query}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_next_prev_url(client: TestClient, token: str):
    # creat multiple users
    create_user(client)
    create_user(client)
    resp = client.get("/users?limit=1", headers={"Authorization": f"Bearer {token}"})
    next_url = resp.json()["next"]
    assert next_url.endswith("/users?limit=1&offset=1")
    # previous
    resp = client.get("/users?limit=1&offset=1", headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    assert prev_url.endswith("/users?limit=1")
    # next
    resp = client.get("/users?limit=1&offset=2", headers={"Authorization": f"Bearer {token}"})
    prev_url = resp.json()["previous"]
    assert prev_url.endswith("/users?limit=1&offset=1")


def test_undefined_sort(client: TestClient, token: str):
    resp = client.get("/users?sort=fake", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["result"] == []


def test_products_pagination(client: TestClient, user, token: str):
    product = create_product(client, user["id"], token)
    resp = client.get(
        f"/products?store={product['store_id']}&category={product['category']}&\
            min_price=0.001&max_price={product['price']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json()["count"] > 0


def test_token_pagination(client: TestClient, user):
    token_data = create_token(client, user, app_id="998")
    permissions = ",".join(token_data["permissions"])
    resp = client.get(
        f"/token?app_id={token_data['app_id']}&redirect_url={token_data['redirect_url']}&permissions={permissions}",
        headers={"Authorization": f"Bearer {token_data['id']}"},
    )
    assert resp.json()["count"] == 1
