def test_no_root(client):
    response = client.get("/")
    assert response.status_code == 404


def test_create_user(client):
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


def test_get_users(client):
    print(client.get("/users").json())
