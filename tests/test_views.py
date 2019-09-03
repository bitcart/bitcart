from typing import Dict, List, Union

from starlette.testclient import TestClient

TEST_XPUB = "tpubDC9zYPoSZUk5W8Rfaex3k324fi1hDLHapbSjPd4gbr7AE8MLSGEy76fNp5m6sVLBy9p2iTjRkiguVyb8iEHCdUBC7SXnhHdHMpXwFcrVMyA"
TEST_XPUB2 = "tpubDD1g867nDN1JyfNAjHNWrL2XNg98y6gM1W82C4nxqxGq5QPEFCtxYLFGgi7GrBwu4TczHRnwXic81BZ2FKBwmKvQdRJpNdfXPtAmtzBkD1A"
TEST_XPUB3 = "tpubDD5MNJWw35y3eoJA7m3kFWsyX5SaUgx2Y3AaGwFk1pjYsHvpgDwRhrStRbCGad8dYzZCkLCvbGKfPuBiG7BabswmLofb7c2yfQFhjqSjaGi"

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

    def process_resp(self, resp, test):
        to_check = self.status_mapping[test["status"]]
        assert resp.status_code == to_check
        if to_check == 200:
            data = resp.json()
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
            self.process_resp(resp, test)

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
    tests = {
        "create": [
            {
                "data": {"username": "test", "password": 12345},
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
            {
                "data": {"username": "test", "password": 12345},
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 2},
            },
            {"data": {}, "status": "bad"},
            {"data": {"username": "test"}, "status": "bad"},
            {"data": {"password": "test"}, "status": "bad"},
        ],
        "get_all": [
            {
                "status": "good",
                "return_data": [
                    {"email": None, "username": "test", "id": 1},
                    {"email": None, "username": "test", "id": 2},
                ],
            }
        ],
        "get_one": [
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
            {"obj_id": "x", "status": "bad"},
            {"obj_id": 3, "status": "not found"},
        ],
        "partial_update": [
            {
                "obj_id": 1,
                "data": {"username": "test1"},
                "status": "good",
                "return_data": {"email": None, "username": "test1", "id": 1},
            },
            {
                "obj_id": 1,
                "data": {"username": "test1", "email": "test@example.com"},
                "status": "good",
                "return_data": {
                    "email": "test@example.com",
                    "username": "test1",
                    "id": 1,
                },
            },
            {
                "obj_id": 1,
                "data": {"username": "test1", "email": "test"},
                "status": "bad",
            },
        ],
        "full_update": [
            {"obj_id": 1, "data": {"username": "test"}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None, "username": "test"}, "status": "bad"},
            {
                "obj_id": 1,
                "data": {"id": 1, "username": "test"},
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
        ],
        "delete": [
            {"obj_id": 3, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {"email": None, "username": "test", "id": 1},
            },
            {"obj_id": 1, "status": "not found"},
        ],
    }


class TestWallets(ViewTestMixin):
    name = "wallets"
    tests = {
        "create": [
            {
                "data": {"name": "test", "user_id": 2, "xpub": ""},
                "status": "good",
                "return_data": {
                    "id": 1,
                    "name": "test",
                    "user_id": 2,
                    "xpub": "",
                    "balance": 0,
                },
            },
            {
                "data": {"name": "test1", "user_id": 2, "xpub": TEST_XPUB},
                "status": "good",
                "return_data": {
                    "id": 2,
                    "name": "test1",
                    "user_id": 2,
                    "xpub": TEST_XPUB,
                    "balance": 0,
                },
            },
            {
                "data": {"name": "test5", "user_id": 2, "xpub": TEST_XPUB2},
                "status": "good",
                "return_data": {
                    "id": 3,
                    "name": "test5",
                    "user_id": 2,
                    "xpub": TEST_XPUB2,
                    "balance": 0,
                },
            },
            {
                "data": {"name": "test1", "user_id": 2, "xpub": TEST_XPUB},
                "status": "bad",
            },
            {"data": {}, "status": "bad"},
            {"data": {"name": "test"}, "status": "bad"},
            {"data": {"xpub": "test"}, "status": "bad"},
            {"data": {"user_id": "test"}, "status": "bad"},
        ],
        "get_all": [
            {
                "status": "good",
                "return_data": [
                    {
                        "name": "test1",
                        "user_id": 2,
                        "xpub": TEST_XPUB,
                        "balance": 0.0,
                        "id": 2,
                    },
                    {
                        "id": 3,
                        "name": "test5",
                        "user_id": 2,
                        "xpub": TEST_XPUB2,
                        "balance": 0,
                    },
                ],
            }
        ],
        "get_one": [
            {"obj_id": 1, "status": "not found"},
            {
                "obj_id": 2,
                "status": "good",
                "return_data": {
                    "name": "test1",
                    "user_id": 2,
                    "xpub": TEST_XPUB,
                    "balance": 0.0,
                    "id": 2,
                },
            },
            {"obj_id": "x", "status": "bad"},
        ],
        "partial_update": [
            {
                "obj_id": 2,
                "data": {"name": "test2", "user_id": 2},
                "status": "good",
                "return_data": {
                    "name": "test2",
                    "user_id": 2,
                    "xpub": TEST_XPUB,
                    "balance": 0.0,
                    "id": 2,
                },
            },
            {"obj_id": 2, "data": {"name": "test3"}, "status": "bad"},
            {"obj_id": 2, "data": {"name": "test2", "user_id": 3}, "status": "bad"},
        ],
        "full_update": [
            {"obj_id": 2, "data": {"name": "test"}, "status": "bad"},
            {"obj_id": 2, "data": {"id": None}, "status": "bad"},
            {"obj_id": 2, "data": {"id": None, "name": "test"}, "status": "bad"},
            {
                "obj_id": 2,
                "data": {"id": 2, "name": "test1", "user_id": 2, "xpub": TEST_XPUB},
                "status": "good",
                "return_data": {
                    "name": "test1",
                    "user_id": 2,
                    "xpub": TEST_XPUB,
                    "balance": 0.0,
                    "id": 2,
                },
            },
        ],
        "delete": [
            {"obj_id": 1, "status": "not found"},
            {
                "obj_id": 2,
                "status": "good",
                "return_data": {
                    "name": "test1",
                    "user_id": 2,
                    "xpub": TEST_XPUB,
                    "balance": 0.0,
                    "id": 2,
                },
            },
            {"obj_id": 2, "status": "not found"},
        ],
    }


class TestStores(ViewTestMixin):
    name = "stores"
    tests = {
        "create": [
            {
                "data": {"name": "test", "wallet_id": 3},
                "status": "good",
                "return_data": {
                    "domain": "",
                    "email": None,
                    "email_host": "",
                    "email_password": "",
                    "email_port": 25,
                    "email_user": "",
                    "id": 1,
                    "name": "test",
                    "template": "",
                    "wallet_id": 3,
                },
            },
            {
                "data": {
                    "name": "test5",
                    "wallet_id": 3,
                    "domain": "example.com",
                    "email": "test@example.com",
                },
                "status": "good",
                "return_data": {
                    "domain": "example.com",
                    "email": "test@example.com",
                    "email_host": "",
                    "email_password": "",
                    "email_port": 25,
                    "email_user": "",
                    "id": 2,
                    "name": "test5",
                    "template": "",
                    "wallet_id": 3,
                },
            },
            {"data": {}, "status": "bad"},
            {"data": {"name": "test"}, "status": "bad"},
            {"data": {"wallet_id": 3}, "status": "bad"},
            {"data": {"email": "test"}, "status": "bad"},
        ],
        "get_all": [
            {
                "status": "good",
                "return_data": [
                    {
                        "domain": "",
                        "email": None,
                        "email_host": "",
                        "email_password": "",
                        "email_port": 25,
                        "email_user": "",
                        "id": 1,
                        "name": "test",
                        "template": "",
                        "wallet_id": 3,
                    },
                    {
                        "domain": "example.com",
                        "email": "test@example.com",
                        "email_host": "",
                        "email_password": "",
                        "email_port": 25,
                        "email_user": "",
                        "id": 2,
                        "name": "test5",
                        "template": "",
                        "wallet_id": 3,
                    },
                ],
            }
        ],
        "get_one": [
            {"obj_id": 3, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {
                    "domain": "",
                    "email": None,
                    "email_host": "",
                    "email_password": "",
                    "email_port": 25,
                    "email_user": "",
                    "id": 1,
                    "name": "test",
                    "template": "",
                    "wallet_id": 3,
                },
            },
            {"obj_id": "x", "status": "bad"},
        ],
        "partial_update": [
            {
                "obj_id": 1,
                "data": {"name": "test2", "wallet_id": 3},
                "status": "good",
                "return_data": {
                    "domain": "",
                    "email": None,
                    "email_host": "",
                    "email_password": "",
                    "email_port": 25,
                    "email_user": "",
                    "id": 1,
                    "name": "test2",
                    "template": "",
                    "wallet_id": 3,
                },
            },
            {
                "obj_id": 1,
                "data": {"name": "test2", "wallet_id": 3, "email": "test1@example.com"},
                "status": "good",
                "return_data": {
                    "domain": "",
                    "email": "test1@example.com",
                    "email_host": "",
                    "email_password": "",
                    "email_port": 25,
                    "email_user": "",
                    "id": 1,
                    "name": "test2",
                    "template": "",
                    "wallet_id": 3,
                },
            },
            {
                "obj_id": 1,
                "data": {"name": "test2", "wallet_id": 3, "email": "test"},
                "status": "bad",
            },
            {"obj_id": 1, "data": {"name": "test3"}, "status": "bad"},
            {"obj_id": 1, "data": {"name": "test2", "user_id": 3}, "status": "bad"},
        ],
        "full_update": [
            {"obj_id": 1, "data": {"name": "test"}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None, "name": "test"}, "status": "bad"},
            {
                "obj_id": 1,
                "data": {"id": 1, "name": "test", "wallet_id": 3},
                "status": "good",
                "return_data": {
                    "domain": "",
                    "email": None,
                    "email_host": "",
                    "email_password": "",
                    "email_port": 25,
                    "email_user": "",
                    "id": 1,
                    "name": "test",
                    "template": "",
                    "wallet_id": 3,
                },
            },
        ],
        "delete": [
            {"obj_id": 3, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {
                    "domain": "",
                    "email": None,
                    "email_host": "",
                    "email_password": "",
                    "email_port": 25,
                    "email_user": "",
                    "id": 1,
                    "name": "test",
                    "template": "",
                    "wallet_id": 3,
                },
            },
            {"obj_id": 1, "status": "not found"},
        ],
    }


class TestProducts(ViewTestMixin):
    name = "products"
    tests = {
        "create": [
            {
                "data": {
                    "title": "test",
                    "amount": 0.5,
                    "quantity": 0.5,
                    "store_id": 2,
                },
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "description": "",
                    "quantity": 0.5,
                    "status": "active",
                    "store_id": 2,
                    "title": "test",
                    "id": 1,
                },
            },
            {
                "data": {
                    "title": "test",
                    "amount": 0.5,
                    "quantity": 0.5,
                    "store_id": 2,
                },
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "description": "",
                    "quantity": 0.5,
                    "status": "active",
                    "store_id": 2,
                    "title": "test",
                    "id": 2,
                },
            },
            {"data": {}, "status": "bad"},
            {"data": {"title": "test"}, "status": "bad"},
            {"data": {"store_id": 3}, "status": "bad"},
            {"data": {"quantity": "test"}, "status": "bad"},
        ],
        "get_all": [
            {
                "status": "good",
                "return_data": [
                    {
                        "amount": 0.5,
                        "description": "",
                        "quantity": 0.5,
                        "status": "active",
                        "store_id": 2,
                        "title": "test",
                        "id": 1,
                    },
                    {
                        "amount": 0.5,
                        "description": "",
                        "quantity": 0.5,
                        "status": "active",
                        "store_id": 2,
                        "title": "test",
                        "id": 2,
                    },
                ],
            }
        ],
        "get_one": [
            {"obj_id": 3, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "description": "",
                    "quantity": 0.5,
                    "status": "active",
                    "store_id": 2,
                    "title": "test",
                    "id": 1,
                },
            },
            {"obj_id": "x", "status": "bad"},
        ],
        "partial_update": [
            {
                "obj_id": 1,
                "data": {
                    "amount": 0.5,
                    "quantity": 0.5,
                    "title": "test1",
                    "store_id": 2,
                },
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "description": "",
                    "quantity": 0.5,
                    "status": "active",
                    "store_id": 2,
                    "title": "test1",
                    "id": 1,
                },
            },
            {
                "obj_id": 1,
                "data": {
                    "amount": 0.2,
                    "quantity": 0.2,
                    "title": "test1",
                    "store_id": 2,
                },
                "status": "good",
                "return_data": {
                    "amount": 0.2,
                    "description": "",
                    "quantity": 0.2,
                    "status": "active",
                    "store_id": 2,
                    "title": "test1",
                    "id": 1,
                },
            },
            {"obj_id": 1, "data": {"title": "test3"}, "status": "bad"},
            {"obj_id": 1, "data": {"title": "test2", "store_id": 3}, "status": "bad"},
        ],
        "full_update": [
            {"obj_id": 1, "data": {"title": "test"}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None, "title": "test"}, "status": "bad"},
            {
                "obj_id": 1,
                "data": {
                    "id": 1,
                    "title": "test",
                    "amount": 0.5,
                    "quantity": 0.5,
                    "store_id": 2,
                },
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "description": "",
                    "quantity": 0.5,
                    "status": "active",
                    "store_id": 2,
                    "title": "test",
                    "id": 1,
                },
            },
        ],
        "delete": [
            {"obj_id": 3, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "description": "",
                    "quantity": 0.5,
                    "status": "active",
                    "store_id": 2,
                    "title": "test",
                    "id": 1,
                },
            },
            {"obj_id": 1, "status": "not found"},
        ],
    }


class TestInvoices(ViewTestMixin):
    name = "invoices"
    tests = {
        "create": [
            {
                "data": {"amount": 0.5, "products": [2]},
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "status": "active",
                    "products": [2],
                    "id": 1,
                },
            },
            {"data": {}, "status": "bad"},
            {"data": {"amount": 0.2}, "status": "bad"},
        ],
        "get_all": [
            {
                "status": "good",
                "return_data": [
                    {"amount": 0.5, "status": "active", "products": [2], "id": 1}
                ],
            }
        ],
        "get_one": [
            {"obj_id": 2, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "status": "active",
                    "products": [2],
                    "id": 1,
                },
            },
            {"obj_id": "x", "status": "bad"},
        ],
        "partial_update": [
            {
                "obj_id": 1,
                "data": {"amount": 0.2, "products": [2]},
                "status": "good",
                "return_data": {
                    "amount": 0.2,
                    "status": "active",
                    "products": [2],
                    "id": 1,
                },
            },
            {"obj_id": 1, "data": {"amount": "test3"}, "status": "bad"},
            {"obj_id": 1, "data": {"amount": "test2"}, "status": "bad"},
        ],
        "full_update": [
            {"obj_id": 1, "data": {"amount": 0.5}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None}, "status": "bad"},
            {"obj_id": 1, "data": {"id": None, "amount": 0.5}, "status": "bad"},
            {
                "obj_id": 1,
                "data": {"id": 1, "amount": 0.5, "products": [2]},
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "status": "active",
                    "products": [2],
                    "id": 1,
                },
            },
        ],
        "delete": [
            {"obj_id": 2, "status": "not found"},
            {
                "obj_id": 1,
                "status": "good",
                "return_data": {
                    "amount": 0.5,
                    "status": "active",
                    "products": [2],
                    "id": 1,
                },
            },
            {"obj_id": 1, "status": "not found"},
        ],
    }


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
    assert client.get("/wallet_history/2").status_code == 404
    resp = client.get("/wallet_history/3")
    client.post("/wallets",json={"name": "test7", "user_id": 2, "xpub": TEST_XPUB3})
    assert resp.status_code == 200
    assert resp.json() == []
    resp1 = client.get("/wallet_history/5")
    assert resp1.status_code == 200
    data2 = resp1.json()
    assert len(data2) == 1
    assert data2[0]['amount'] == '0.01'
    assert data2[0]['txid'] == 'ee4f0c4405f9ba10443958f5c6f6d4552a69a80f3ec3bed1c3d4c98d65abe8f3'
    resp2 = client.get("/wallet_history/0")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 1



def test_create_token(client: TestClient):
    assert (
        client.post("/token", json={"username": "test", "password": 123456}).status_code
        == 401
    )
    assert (
        client.post("/token", json={"username": "test1", "password": 123456}).status_code
        == 401
    )
    resp = client.post("/token", json={"username": "test", "password": 12345})
    assert resp.status_code == 200
    assert resp.json().get("token")
