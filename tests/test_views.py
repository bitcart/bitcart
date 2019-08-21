from starlette.testclient import TestClient


def test_no_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 404


def test_create_user(client: TestClient):
    user = client.post(
        "/users",
        json={
            "username": "test",
            "password": 12345})
    assert user.status_code == 200
    user_json = user.json()
    assert user_json["email"] is None
    assert user_json["username"] == "test"
    assert not user_json.get("password")
    assert not user_json.get("hashed_password")
    assert client.post("/users", json={}).status_code == 422
    assert client.post(
        "/users",
        json={
            "username": "test"}).status_code == 422
    assert client.post(
        "/users",
        json={
            "password": "test"}).status_code == 422


def test_get_users(client: TestClient):
    resp = client.get("/users")
    assert resp.status_code == 200
    assert resp.json() == [{"email": None, "username": "test", "id": 1}]


def test_get_user(client: TestClient):
    resp = client.get("/users/1")
    assert resp.status_code == 200
    assert resp.json() == {"email": None, "username": "test", "id": 1}
    assert client.get("/users/x").status_code == 422
    assert client.get("/users/2").status_code == 404


def test_partial_update_user(client: TestClient):
    resp = client.patch("/users/1", json={"username": "test1"})
    assert resp.status_code == 200
    assert resp.json() == {"email": None, "username": "test1", "id": 1}
    resp2 = client.patch(
        "/users/1",
        json={
            "username": "test1",
            "email": "test@example.com"})
    assert resp2.status_code == 200
    assert resp2.json() == {
        "email": "test@example.com",
        "username": "test1",
        "id": 1}
    assert client.patch(
        "/users/1",
        json={
            "username": "test1",
            "email": "test"}).status_code == 422


def test_full_update_user(client: TestClient):
    assert client.put("/users/1", json={"username": "test"}).status_code == 422
    assert client.put("/users/1", json={"id": None}).status_code == 422
    assert client.put(
        "/users/1",
        json={
            "id": None,
            "username": "test"}).status_code == 422
    resp = client.put("/users/1", json={"id": 1, "username": "test"})
    assert resp.status_code == 200
    assert resp.json() == {
        "email": None,
        "username": "test",
        "id": 1}


def test_delete_user(client: TestClient):
    assert client.delete("/users/2").status_code == 404
    resp = client.delete("/users/1")
    assert resp.status_code == 200
    assert resp.json() == {
        "email": None,
        "username": "test",
        "id": 1}
    assert client.get("/users").json() == []
    assert client.get("/users/1").status_code == 404
