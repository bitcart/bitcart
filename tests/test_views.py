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

    def test_create(self, client: TestClient):
        for test in self.tests["create"]:
            resp = client.post(f"/{self.name}", json=test["data"])
            self.process_resp(resp, test)

    def test_get_all(self, client: TestClient):
        for test in self.tests["get_all"]:
            resp = client.get(f"/{self.name}")
            self.process_resp(resp, test, True)

    def test_get_one(self, client: TestClient):
        for test in self.tests["get_one"]:
            resp = client.get(f"/{self.name}/{test['obj_id']}")
            self.process_resp(resp, test)

    def test_partial_update(self, client: TestClient):
        for test in self.tests["partial_update"]:
            resp = client.patch(f"/{self.name}/{test['obj_id']}", json=test["data"])
            self.process_resp(resp, test)

    def test_full_update(self, client: TestClient):
        for test in self.tests["full_update"]:
            resp = client.put(f"/{self.name}/{test['obj_id']}", json=test["data"])
            self.process_resp(resp, test)

    def test_delete(self, client: TestClient):
        for test in self.tests["delete"]:
            resp = client.delete(f"/{self.name}/{test['obj_id']}")
            self.process_resp(resp, test)


class TestUsers(ViewTestMixin):
    name = "users"
    tests = json.loads(open("tests/fixtures/users.json").read())


class TestWallets(ViewTestMixin):
    name = "wallets"
    tests = json.loads(open("tests/fixtures/wallets.json").read())


class TestStores(ViewTestMixin):
    name = "stores"
    tests = json.loads(open("tests/fixtures/stores.json").read())


class TestProducts(ViewTestMixin):
    name = "products"
    tests = json.loads(open("tests/fixtures/products.json").read())


class TestInvoices(ViewTestMixin):
    name = "invoices"
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


def test_wallet_history(client: TestClient):
    assert client.get("/wallet_history/1").status_code == 404
    assert client.get("/wallet_history/3").status_code == 404
    resp = client.get("/wallet_history/2")
    client.post("/wallets", json={"name": "test7", "user_id": 2, "xpub": TEST_XPUB})
    assert resp.status_code == 200
    assert resp.json() == []
    resp1 = client.get("/wallet_history/4")
    assert resp1.status_code == 200
    data2 = resp1.json()
    assert len(data2) == 1
    assert data2[0]["amount"] == "0.01"
    assert (
        data2[0]["txid"]
        == "ee4f0c4405f9ba10443958f5c6f6d4552a69a80f3ec3bed1c3d4c98d65abe8f3"
    )
    resp2 = client.get("/wallet_history/0")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1


def test_create_token(client: TestClient):
    assert (
        client.post("/token", json={"username": "test", "password": 123456}).status_code
        == 401
    )
    assert (
        client.post(
            "/token", json={"username": "test1", "password": 123456}
        ).status_code
        == 401
    )
    resp = client.post("/token", json={"username": "test", "password": 12345})
    assert resp.status_code == 200
    assert resp.json().get("token")
