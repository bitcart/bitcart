import json as json_module
from typing import Dict, List, Union

import pytest
from starlette.testclient import TestClient

from tests.helper import create_store


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

    def data_update(self, data):
        pass

    def handle_get_all(self, data, test):
        if self.name == "users":
            # special handle for users due to user fixtures
            assert data["count"] >= len(test["return_data"])
        else:
            assert data["count"] == len(test["return_data"])
        assert not data["previous"]
        assert not data["next"]
        assert isinstance(data["result"], list)
        data = data["result"]
        return data

    def process_data(self, data):
        if isinstance(data, list):
            for d in data:
                if isinstance(d, dict):
                    if self.invoice:
                        assert d.get("payments")
                    assert "created" in d
                    d.pop("created", None)
                    d.pop("end_date", None)
                    d.pop("payments", None)
                    d.pop("time_left", None)
        elif isinstance(data, dict):
            if self.invoice:
                assert data.get("payments")
            assert "created" in data
            data.pop("created", None)
            data.pop("end_date", None)
            data.pop("payments", None)
            data.pop("time_left", None)

    def process_resp(self, resp, test, get_all=False):
        to_check = self.status_mapping[test["status"]]
        assert resp.status_code == to_check
        if to_check == 200:
            data = resp.json()
            if get_all:
                data = self.handle_get_all(data, test)
            self.process_data(data)
            if self.name == "users":
                if isinstance(data, int):
                    assert data >= test["return_data"]
                else:
                    assert all([item in data for item in test["return_data"]])
            else:
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
            self.data_update(test)
            resp = self.send_request(f"/{self.name}", client, json=test["data"], method="post", token=token)
            self.process_resp(resp, test)

    def test_get_all(self, client: TestClient, token: str):  # all responses are sorted in creation order
        for test in self.tests["get_all"]:
            self.data_update(test)
            resp = self.send_request(f"/{self.name}", client, token=token)
            self.process_resp(resp, test, True)

    def test_get_count(self, client: TestClient, token: str):
        for test in self.tests["get_count"]:
            self.data_update(test)
            resp = self.send_request(f"/{self.name}/count", client, token=token)
            self.process_resp(resp, test)

    def test_get_one(self, client: TestClient, token: str):
        for test in self.tests["get_one"]:
            self.data_update(test)
            resp = self.send_request(f"/{self.name}/{test['obj_id']}", client, token=token)
            self.process_resp(resp, test)

    def test_partial_update(self, client: TestClient, token: str):
        for test in self.tests["partial_update"]:
            self.data_update(test)
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
            self.data_update(test)
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
            self.data_update(test)
            resp = self.send_request(f"/{self.name}/{test['obj_id']}", client, method="delete", token=token)
            self.process_resp(resp, test)


class TestUsers(ViewTestMixin):
    name = "users"
    auth = True
    tests = json_module.loads(open("tests/fixtures/data/users.json").read())


class TestDiscounts(ViewTestMixin):
    name = "discounts"
    auth = True
    tests = json_module.loads(open("tests/fixtures/data/discounts.json").read())


class TestNotifications(ViewTestMixin):
    name = "notifications"
    auth = True
    tests = json_module.loads(open("tests/fixtures/data/notifications.json").read())


class TestTemplates(ViewTestMixin):
    name = "templates"
    auth = True
    tests = json_module.loads(open("tests/fixtures/data/templates.json").read())


class TestWallets(ViewTestMixin):
    name = "wallets"
    auth = True
    tests = json_module.loads(open("tests/fixtures/data/wallets.json").read())


class TestStores(ViewTestMixin):
    name = "stores"
    auth = True
    tests = json_module.loads(open("tests/fixtures/data/stores.json").read())

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, wallet, notification):
        pass


class TestProducts(ViewTestMixin):
    name = "products"
    json_encoding = False
    auth = True
    tests = json_module.loads(open("tests/fixtures/data/products.json").read())

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, store, discount):
        pass


class TestInvoices(ViewTestMixin):
    name = "invoices"
    auth = True
    invoice = True
    tests = json_module.loads(open("tests/fixtures/data/invoices.json").read())

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, client, user, token, product):
        create_store(client, user, token, custom_store_attrs={"wallets": []})
