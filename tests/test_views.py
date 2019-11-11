import json
from typing import Dict, List, Union

from starlette.testclient import TestClient

TEST_XPUB = "tpubDD5MNJWw35y3eoJA7m3kFWsyX5SaUgx2Y3AaGwFk1pjYsHvpgDwRhrStRbCGad8dYzZCkLCvbGKfPuBiG7BabswmLofb7c2yfQFhjqSjaGi"


class ViewTestMixin:
    """Base class for all modelview tests, as they mostly don't differ

    You must set some parameters unset in this class for it to work in your subclass
    """

    status_mapping: Dict[Union[str, bool], int] = {
        "good": 200,
        "bad": 422,
        "not found": 404,
        True: 200,
        False: 422,
    }
    auth: bool = False
    name: str  # name used in endpoints
    tests: Dict[str, List[dict]]
    """dict with keys corresponding to testing function, each key is a list of
    dicts, where each dict must have status key, return_data key if status
    is good, obj_id if function requires it, and data if function sends it
    """

    def process_resp(self, resp, test, get_all=False):
        to_check = self.status_mapping[test["status"]]
        assert resp.status_code == to_check
        if to_check == 200:
            data = resp.json()
            if get_all:
                assert data["count"] == len(test["return_data"])
                assert not data["previous"]
                assert not data["next"]
                assert isinstance(data["result"], list)
                data = data["result"]
            if isinstance(data, list):
                for d in data:
                    if isinstance(d, dict):
                        if d.get("date"):
                            d.pop("date")
                        try:
                            d.pop("bitcoin_address")
                            d.pop("bitcoin_url")
                        except KeyError:
                            pass
            elif isinstance(data, dict):
                if data.get("date"):
                    data.pop("date")
                try:
                    data.pop("bitcoin_address")
                    data.pop("bitcoin_url")
                except KeyError:
                    pass
            assert data == test["return_data"]

    def send_request(self, url, client, json={}, method="get", token=""):
        headers = {}
        if self.auth:
            headers["Authorization"] = f"Bearer {token}"
        return client.request(method, url, json=json, headers=headers)

    def test_create(self, client: TestClient, token: str):
        for test in self.tests["create"]:
            resp = self.send_request(
                f"/{self.name}", client, json=test["data"], method="post", token=token
            )
            self.process_resp(resp, test)

    def test_get_all(self, client: TestClient, token: str):
        for test in self.tests["get_all"]:
            resp = self.send_request(f"/{self.name}", client, token=token)
            self.process_resp(resp, test, True)

    def test_get_one(self, client: TestClient, token: str):
        for test in self.tests["get_one"]:
            resp = self.send_request(
                f"/{self.name}/{test['obj_id']}", client, token=token
            )
            self.process_resp(resp, test)

    def test_partial_update(self, client: TestClient, token: str):
        for test in self.tests["partial_update"]:
            resp = self.send_request(
                f"/{self.name}/{test['obj_id']}",
                client,
                json=test["data"],
                method="patch",
                token=token,
            )
            self.process_resp(resp, test)

    def test_full_update(self, client: TestClient, token: str):
        for test in self.tests["full_update"]:
            resp = self.send_request(
                f"/{self.name}/{test['obj_id']}",
                client,
                json=test["data"],
                method="put",
                token=token,
            )
            self.process_resp(resp, test)

    def test_delete(self, client: TestClient, token: str):
        for test in self.tests["delete"]:
            resp = self.send_request(
                f"/{self.name}/{test['obj_id']}", client, method="delete", token=token
            )
            self.process_resp(resp, test)


class TestUsers(ViewTestMixin):
    name = "users"
    auth = True
    tests = json.loads(open("tests/fixtures/users.json").read())


class TestWallets(ViewTestMixin):
    name = "wallets"
    auth = True
    tests = json.loads(open("tests/fixtures/wallets.json").read())


class TestStores(ViewTestMixin):
    name = "stores"
    auth = True
    tests = json.loads(open("tests/fixtures/stores.json").read())


class TestProducts(ViewTestMixin):
    name = "products"
    auth = True
    tests = json.loads(open("tests/fixtures/products.json").read())


class TestInvoices(ViewTestMixin):
    name = "invoices"
    auth = True
    tests = json.loads(open("tests/fixtures/invoices.json").read())


def test_no_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 404


def test_rate(client: TestClient):
    resp = client.get("/rate")
    data = resp.json()
    assert resp.status_code == 200
    assert isinstance(data, float)
    assert data > 0


def test_wallet_history(client: TestClient, token: str):
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/wallet_history/1", headers=headers).status_code == 404
    assert client.get("/wallet_history/3", headers=headers).status_code == 404
    resp = client.get("/wallet_history/2", headers=headers)
    client.post(
        "/wallets",
        json={"name": "test7", "user_id": 2, "xpub": TEST_XPUB},
        headers=headers,
    ).json()
    assert resp.status_code == 200
    assert resp.json() == []
    resp1 = client.get("/wallet_history/4", headers=headers)
    assert resp1.status_code == 200
    data2 = resp1.json()
    assert len(data2) == 1
    assert data2[0]["amount"] == "0.01"
    assert (
        data2[0]["txid"]
        == "ee4f0c4405f9ba10443958f5c6f6d4552a69a80f3ec3bed1c3d4c98d65abe8f3"
    )
    resp2 = client.get("/wallet_history/0", headers=headers)
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1


def test_create_token(client: TestClient):
    assert (
        client.post(
            "/token", json={"username": "test44", "password": 123456}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/token", json={"username": "test1", "password": 123456}
        ).status_code
        == 401
    )
    resp = client.post("/token", json={"username": "test44", "password": 12345})
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("access_token")
    assert j["token_type"] == "bearer"


def test_noauth(client: TestClient):
    assert client.get("/users").status_code == 401
    assert client.get("/wallets").status_code == 401
    assert client.get("/stores").status_code == 401
    assert client.get("/products").status_code == 401
    assert client.get("/invoices").status_code == 401
    assert (
        client.post(
            "/users", json={"username": "noauth", "password": "noauth"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/token", json={"username": "noauth", "password": "noauth"}
        ).status_code
        == 200
    )


def test_superuseronly(client: TestClient, token: str):
    token_usual = client.post(
        "/token", json={"username": "noauth", "password": "noauth"}
    ).json()["access_token"]
    assert (
        client.get(
            "/users", headers={"Authorization": f"Bearer {token_usual}"}
        ).status_code
        == 401
    )
    assert (
        client.get("/users", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )

