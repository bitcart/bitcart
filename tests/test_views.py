import json as json_module
from datetime import datetime, timedelta
from typing import Dict, List, Union

import pytest
from fastapi.encoders import jsonable_encoder
from starlette.testclient import TestClient

from api import settings, templates
from api.ext import tor as tor_ext

TEST_XPUB = "tpubDD5MNJWw35y3eoJA7m3kFWsyX5SaUgx2Y3AaGwFk1pjYsHvpgDwRhrStRbCGad8dYzZCkLCvbGKfPuBiG7BabswmLofb7c2yfQFhjqSjaGi"
LIMITED_USER_DATA = {
    "email": "testauthlimited@example.com",
    "password": "test12345",
}


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


class TestNotifications(ViewTestMixin):
    name = "notifications"
    auth = True
    tests = json_module.loads(open("tests/fixtures/notifications.json").read())


class TestTemplates(ViewTestMixin):
    name = "templates"
    auth = True
    tests = json_module.loads(open("tests/fixtures/templates.json").read())


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


def test_docs_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200


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


def test_crud_count(client: TestClient, token: str):
    resp = client.get("/crud/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {
        "wallets": 3,
        "stores": 1,
        "discounts": 1,
        "products": 1,
        "invoices": 0,
        "notifications": 1,
        "templates": 1,
        "balance": 0.01,
    }


def test_categories(client: TestClient):
    assert client.get("/categories").status_code == 422
    resp = client.get("/categories?store=1")
    resp2 = client.get("/categories?store=2")
    assert resp.status_code == 200
    assert resp.json() == ["all"]
    assert resp2.status_code == 200
    assert set(resp2.json()) == set(
        ["all", "Test"]
    )  # TODO: make endpoint output order consistent


def check_token(result):
    assert isinstance(result, dict)
    assert result["user_id"] == 1
    assert result["app_id"] == result["redirect_url"] == ""
    assert result["permissions"] == ["full_control"]


def test_token(client: TestClient, token: str):
    assert client.get("/token").status_code == 401
    resp = client.get("/token", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["count"] == 1
    assert not j["previous"]
    assert not j["next"]
    result = j["result"]
    assert isinstance(result, list)
    assert len(result) == 1
    result = result[0]
    check_token(result)


def test_token_current(client: TestClient, token: str):
    assert client.get("/token/current").status_code == 401
    resp = client.get("/token/current", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    j = resp.json()
    check_token(j)
    assert j["id"] == token


def test_token_count(client: TestClient, token: str):
    assert client.get("/token/count").status_code == 401
    resp = client.get("/token/count", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == 1


def test_patch_token(client: TestClient, token: str):
    assert client.patch(f"/token/{token}").status_code == 401
    assert (
        client.patch(
            "/token/{token}",
            json={"redirect_url": "test"},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 404
    )
    resp = client.patch(
        f"/token/{token}",
        json={"redirect_url": "google.com:443"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    j = resp.json()
    assert j["redirect_url"] == "google.com:443"
    assert j["id"] == token


def test_create_tokens(client: TestClient, token: str):
    assert client.post("/token").status_code == 401
    assert (
        client.post("/token", json={"email": "test1", "password": "test2"}).status_code
        == 401
    )
    assert (
        client.post(
            "/token", json={"email": "testauth@example.com", "password": "test12345"}
        ).status_code
        == 200
    )
    assert (
        client.post("/token", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )
    # Selective permissions control is done by client, not by server
    resp = client.post(
        "/token",
        json={"permissions": ["store_management:2"],},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    j = resp.json()
    assert j["permissions"] == ["store_management:2"]
    # Limited token can't access higher scopes
    assert (
        client.post(
            "/token",
            json={"permissions": ["store_management"]},
            headers={"Authorization": f"Bearer {j['id']}"},
        ).status_code
        == 403
    )

    assert client.post("/users", json=LIMITED_USER_DATA).status_code == 200
    # Strict mode: non-superuser user can't create superuser token
    assert (
        client.post(
            "/token", json={**LIMITED_USER_DATA, "permissions": ["server_management"]}
        ).status_code
        == 422
    )
    # Non-strict mode: silently removes server_management permission
    resp = client.post(
        "/token",
        json={
            **LIMITED_USER_DATA,
            "permissions": ["server_management"],
            "strict": False,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["permissions"] == []


def test_delete_token(client: TestClient, token: str):
    assert client.delete("/token/1").status_code == 401
    assert (
        client.delete(
            "/token/1", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 404
    )
    all_tokens = client.get(
        "/token", headers={"Authorization": f"Bearer {token}"}
    ).json()["result"]
    for token_data in all_tokens:
        if token_data["id"] == token:
            continue  # skip our token
        resp = client.delete(
            f"/token/{token_data['id']}", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.json() == token_data
    test_token_count(client, token)


def test_management_commands(client: TestClient, token: str):
    assert client.post("/manage/update").status_code == 401
    limited_user_token = client.post("/token", json=LIMITED_USER_DATA).json()["id"]
    assert (
        client.post(
            "/manage/update", headers={"Authorization": f"Bearer {limited_user_token}"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/manage/update", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/manage/cleanup", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/manage/daemons", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )


def test_policies(client: TestClient, token: str):
    resp = client.get("/manage/policies")
    assert resp.status_code == 200
    assert resp.json() == {"disable_registration": False, "discourage_index": False}
    assert client.post("/manage/policies").status_code == 401
    resp = client.post(
        "/manage/policies",
        json={"disable_registration": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"disable_registration": True, "discourage_index": False}
    # Test for loading data from db instead of loading scheme's defaults
    assert client.get("/manage/policies").json() == {
        "disable_registration": True,
        "discourage_index": False,
    }
    resp = client.post(
        "/manage/policies",
        json={"disable_registration": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"disable_registration": False, "discourage_index": False}
    resp = client.get("/manage/stores")
    assert resp.status_code == 200
    assert resp.json() == {"pos_id": 1}
    assert client.post("/manage/stores").status_code == 401
    resp = client.post(
        "/manage/stores",
        json={"pos_id": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"pos_id": 2}
    assert client.get("/manage/stores").json() == {"pos_id": 2}
    resp = client.post(
        "/manage/stores",
        json={"pos_id": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"pos_id": 1}


def test_no_token_management(client: TestClient, token: str):
    limited_user_token = client.post("/token", json=LIMITED_USER_DATA).json()["id"]
    assert (
        client.get(
            "/token/current", headers={"Authorization": f"Bearer {limited_user_token}"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/token", headers={"Authorization": f"Bearer {limited_user_token}"}
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/token/count", headers={"Authorization": f"Bearer {limited_user_token}"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/token/{limited_user_token}",
            headers={"Authorization": f"Bearer {limited_user_token}"},
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/token/{limited_user_token}",
            headers={"Authorization": f"Bearer {limited_user_token}"},
        ).status_code
        == 403
    )


def test_notification_list(client: TestClient):
    resp = client.get("/notifications/list")
    assert resp.status_code == 200
    assert resp.json() == {
        "count": len(settings.notifiers),
        "next": None,
        "previous": None,
        "result": list(settings.notifiers.keys()),
    }


def test_notification_schema(client: TestClient):
    resp = client.get("/notifications/schema")
    assert resp.status_code == 200
    assert resp.json() == settings.notifiers


def test_template_list(client: TestClient):
    resp = client.get("/templates/list")
    assert resp.status_code == 200
    assert resp.json() == {
        "count": len(templates.templates_strings),
        "next": None,
        "previous": None,
        "result": templates.templates_strings,
    }
    resp1 = client.get("/templates/list?show_all=true")
    result = [
        v for template_set in templates.templates_strings.values() for v in template_set
    ]
    assert resp1.status_code == 200
    assert resp1.json() == {
        "count": len(result),
        "next": None,
        "previous": None,
        "result": result,
    }
    resp2 = client.get("/templates/list?applicable_to=product")
    assert resp2.status_code == 200
    assert resp2.json() == {
        "count": len(templates.templates_strings["product"]),
        "next": None,
        "previous": None,
        "result": templates.templates_strings["product"],
    }
    resp3 = client.get("/templates/list?applicable_to=notfound")
    assert resp3.status_code == 200
    assert resp3.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "result": [],
    }


def test_services(client: TestClient, token: str):
    resp = client.get("/services")
    assert resp.status_code == 200
    assert resp.json() == tor_ext.TorService.anonymous_services_dict
    resp2 = client.get("/services", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json() == jsonable_encoder(tor_ext.TorService.services_dict)


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
    websocket = async_client.websocket_connect(f"/ws/invoices/{invoice_id}")
    await websocket.connect()
    await check_ws_response(websocket)
    websocket2 = async_client.websocket_connect(
        f"/ws/invoices/{invoice_id}"
    )  # test if after invoice was completed websocket returns immediately
    await websocket2.connect()
    await check_ws_response(websocket2)
    with pytest.raises(Exception):
        websocket = async_client.websocket_connect(f"/ws/invoices/555")
        await websocket.connect()
        await check_ws_response(websocket)
