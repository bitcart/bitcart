import json as json_module
from datetime import datetime, timedelta
from typing import Dict, List, Union

import jwt
import pytest
from starlette.testclient import TestClient

from api.settings import ALGORITHM, SECRET_KEY

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
    invoice: bool = False
    json_encoding: bool = True
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
                        if self.invoice:
                            assert d.get("payments")
                        d.pop("date", None)
                        d.pop("end_date", None)
                        d.pop("payments", None)
            elif isinstance(data, dict):
                if self.invoice:
                    assert data.get("payments")
                data.pop("date", None)
                data.pop("end_date", None)
                data.pop("payments", None)
            assert data == test["return_data"]

    def send_request(self, url, client, json={}, method="get", token=""):
        headers = {}
        if self.auth:
            headers["Authorization"] = f"Bearer {token}"
        kwargs = {"headers": headers}
        if self.json_encoding:
            kwargs["json"] = json
        else:
            kwargs["data"] = {"data": json_module.dumps(json)}
        return client.request(method, url, **kwargs)

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

    def test_get_count(self, client: TestClient, token: str):
        for test in self.tests["get_count"]:
            resp = self.send_request(f"/{self.name}/count", client, token=token)
            self.process_resp(resp, test)

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
    tests = json_module.loads(open("tests/fixtures/users.json").read())


class TestDiscounts(ViewTestMixin):
    name = "discounts"
    auth = True
    tests = json_module.loads(open("tests/fixtures/discounts.json").read())


class TestWallets(ViewTestMixin):
    name = "wallets"
    auth = True
    tests = json_module.loads(open("tests/fixtures/wallets.json").read())


class TestStores(ViewTestMixin):
    name = "stores"
    auth = True
    tests = json_module.loads(open("tests/fixtures/stores.json").read())


class TestProducts(ViewTestMixin):
    name = "products"
    json_encoding = False
    auth = True
    tests = json_module.loads(open("tests/fixtures/products.json").read())


class TestInvoices(ViewTestMixin):
    name = "invoices"
    auth = True
    invoice = True
    tests = json_module.loads(open("tests/fixtures/invoices.json").read())


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
    assert client.get("/wallet_history/4", headers=headers).status_code == 404
    resp = client.get("/wallet_history/2", headers=headers)
    client.post(
        "/wallets", json={"name": "test7", "xpub": TEST_XPUB}, headers=headers
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
            "/token", json={"email": "test44@example.com", "password": 123456}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/token", json={"email": "test1@example.com", "password": 123456}
        ).status_code
        == 401
    )
    resp = client.post(
        "/token", json={"email": "test44@example.com", "password": 12345}
    )
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("access_token")
    assert j.get("refresh_token")
    assert j["token_type"] == "bearer"


def test_refresh_token(client: TestClient):
    resp = client.post(
        "/token", json={"email": "test44@example.com", "password": 12345}
    )
    assert resp.status_code == 200
    resp = resp.json()
    assert resp.get("refresh_token")
    resp1 = client.post("/refresh_token", json={"token": resp["refresh_token"]})
    assert resp1.status_code == 200
    j = resp1.json()
    assert j.get("access_token")
    assert j.get("refresh_token")
    assert j["token_type"] == "bearer"


def test_noauth(client: TestClient):
    assert client.get("/users").status_code == 401
    assert client.get("/wallets").status_code == 401
    assert client.get("/stores").status_code == 401
    assert client.get("/products").status_code == 401
    assert client.get("/invoices").status_code == 401
    assert (
        client.post(
            "/users", json={"email": "noauth@example.com", "password": "noauth"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/token", json={"email": "noauth@example.com", "password": "noauth"}
        ).status_code
        == 200
    )


def test_superuseronly(client: TestClient, token: str):
    token_usual = client.post(
        "/token", json={"email": "noauth@example.com", "password": "noauth"}
    ).json()["access_token"]
    assert (
        client.get(
            "/users", headers={"Authorization": f"Bearer {token_usual}"}
        ).status_code
        == 403
    )
    assert (
        client.get("/users", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )


def test_invalidjwt(client: TestClient, token: str):
    assert (
        client.get(
            "/wallets", headers={"Authorization": f"Bearer {token[0:5]}"}
        ).status_code
        == 401
    )
    invalid_username_jwt = jwt.encode(
        {"sub": "wronguser", "exp": datetime.utcnow() + timedelta(minutes=10)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    ).decode()
    assert (
        client.get(
            "/wallets", headers={"Authorization": f"Bearer {invalid_username_jwt}"}
        ).status_code
        == 401
    )
    no_username_jwt = jwt.encode(
        {"sub": None, "exp": datetime.utcnow() + timedelta(minutes=10)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    ).decode()
    assert (
        client.get(
            "/wallets", headers={"Authorization": f"Bearer {no_username_jwt}"}
        ).status_code
        == 401
    )
    expired_jwt = jwt.encode(
        {"sub": "testauth", "exp": -999}, SECRET_KEY, algorithm=ALGORITHM
    ).decode()
    assert (
        client.get(
            "/wallets", headers={"Authorization": f"Bearer {expired_jwt}"}
        ).status_code
        == 401
    )


def test_users_me(client: TestClient, token: str):
    assert client.get("/users/me").status_code == 401
    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    j = resp.json()
    assert j == {"is_superuser": True, "id": 1, "email": "testauth@example.com"}


def test_wallets_balance(client: TestClient, token: str):
    assert client.get("/wallets/balance").status_code == 401
    resp = client.get("/wallets/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == 0.01


def test_fiatlist(client: TestClient):
    resp = client.get("/fiatlist")
    assert resp.status_code == 200
    j1 = resp.json()
    assert isinstance(j1, list)
    assert "BTC" in j1
    assert "USD" in j1
    resp2 = client.get("/fiatlist?query=b")
    assert resp2.status_code == 200
    j2 = resp2.json()
    assert isinstance(j2, list)
    assert "BTC" in j2
    resp3 = client.get("/fiatlist?query=U")
    assert resp3.status_code == 200
    j3 = resp3.json()
    assert isinstance(j3, list)
    assert "USD" in j3


async def check_ws_response(ws):
    data = await ws.receive_json()
    assert data == {"status": "test"}


async def check_ws_response2(ws):
    data = await ws.receive_json()
    assert data == {"status": "success", "balance": "0.01"}


def test_ping_email(client: TestClient, token: str):
    resp0 = client.get("/stores/55/ping")
    assert resp0.status_code == 401
    resp = client.get("/stores/55/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
    resp1 = client.get("/stores/2/ping", headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 200
    assert resp1.json() == False


@pytest.mark.asyncio
async def test_wallet_ws(async_client, token: str):
    r = await async_client.post(
        "/wallets",
        json={"name": "testws1", "xpub": TEST_XPUB},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    wallet_id = r.json()["id"]
    websocket = async_client.websocket_connect(f"/ws/wallets/{wallet_id}?token={token}")
    await websocket.connect()
    await check_ws_response2(websocket)
    with pytest.raises(Exception):
        websocket = async_client.websocket_connect(f"/ws/wallets/{wallet_id}")
        await websocket.connect()
        await check_ws_response2(websocket)
    with pytest.raises(Exception):
        websocket = async_client.websocket_connect(f"/ws/wallets/{wallet_id}?token=x")
        await websocket.connect()
        await check_ws_response2(websocket)
    with pytest.raises(Exception):
        websocket = async_client.websocket_connect(f"/ws/wallets/555?token={token}")
        await websocket.connect()
        await check_ws_response2(websocket)


@pytest.mark.asyncio
async def test_invoice_ws(async_client, token: str):
    r = await async_client.post(
        "/invoices",
        json={"store_id": 2, "price": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    invoice_id = r.json()["id"]
    websocket = async_client.websocket_connect(
        f"/ws/invoices/{invoice_id}?token={token}"
    )
    await websocket.connect()
    await check_ws_response(websocket)
    with pytest.raises(Exception):
        websocket = async_client.websocket_connect(f"/ws/invoices/{invoice_id}")
        await websocket.connect()
        await check_ws_response(websocket)
    with pytest.raises(Exception):
        websocket = async_client.websocket_connect(f"/ws/invoices/{invoice_id}?token=x")
        await websocket.connect()
        await check_ws_response(websocket)
    with pytest.raises(Exception):
        websocket = async_client.websocket_connect(f"/ws/invoices/555?token={token}")
        await websocket.connect()
        await check_ws_response(websocket)
