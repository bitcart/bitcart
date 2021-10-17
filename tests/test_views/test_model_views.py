import json as json_module
import traceback
from datetime import datetime

import pytest
from httpx import AsyncClient as TestClient

from api.constants import ID_LENGTH, PUBLIC_ID_LENGTH

pytestmark = pytest.mark.anyio


class ViewTestMixin:
    """Base class for all modelview tests, as they mostly don't differ

    You must set some parameters unset in this class for it to work in your subclass
    """

    name: str  # name used in endpoints
    create_auth: bool = True
    get_one_auth: bool = True
    id_length: int = ID_LENGTH
    json_encoding: bool = True

    @property
    def create_data(self):
        return self.tests["create"]

    @property
    def patch_data(self):
        return self.tests["patch"]

    @property
    def expected_resp(self):
        return self.tests["response"]

    @property
    def expected_count(self):
        return self.tests["count"]

    async def create_object(self, client, token):
        # Create initial object for other tests
        print("O1")
        if self.create_auth:
            assert (await client.post(f"/{self.name}", **self.prepare_data(self.create_data))).status_code == 401
        print("O2")
        resp = await client.post(
            f"/{self.name}", **self.prepare_data(self.create_data), headers={"Authorization": f"Bearer {token}"}
        )
        print("O3")
        assert resp.status_code == 200
        print("O4")
        self.data = resp.json()
        print("O5")

    @pytest.fixture(autouse=True)
    async def setup(self, client: TestClient, token: str, anyio_backend):
        print("CALL")
        try:
            await self.create_object(client, token)
            print(self.data)
        except:
            print(traceback.format_exc())

    def check_pagination_response(self, data):
        assert data["count"] == self.expected_count
        assert not data["previous"]
        assert not data["next"]
        assert isinstance(data["result"], list)
        return data["result"]

    def _check_key(self, data, key, key_type):
        assert key in data
        assert isinstance(data[key], key_type)

    def check_id(self, data, id_length):
        self._check_key(data, "id", str)
        assert len(data["id"]) == id_length

    def check_created(self, data):
        self._check_key(data, "created", str)
        try:
            datetime.fromisoformat(data["created"])
        except ValueError:
            pytest.fail(f"Invalid created field: {data['created']}")

    @property
    def object_id(self):
        return self.data["id"]

    def check_data(self):
        self.check_id(self.data, id_length=self.id_length)
        self.check_created(self.data)

    # The actual create is done by data fixture once
    async def test_create(self):
        print("O", getattr(self, "data", None))
        assert self.data.items() > self.expected_resp.items()
        self.check_data()

    def prepare_data(self, data):
        if self.json_encoding:
            return {"json": data}
        else:
            return {"data": {"data": json_module.dumps(data)}}

    async def test_get_all(self, client: TestClient, token: str):
        assert (await client.get(f"/{self.name}")).status_code == 401
        resp = await client.get(f"/{self.name}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        objects = self.check_pagination_response(resp.json())
        # The objects list is ordered by created date; first object is the last object created
        assert objects[0] == self.data

    async def test_get_count(self, client: TestClient, token: str):
        assert (await client.get(f"/{self.name}/count")).status_code == 401
        resp = await client.get(f"/{self.name}/count", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == self.expected_count

    async def test_get_one(self, client: TestClient, token: str):
        if self.get_one_auth:
            assert (await client.get(f"/{self.name}/{self.object_id}")).status_code == 401
        resp = await client.get(f"/{self.name}/{self.object_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == self.data

    async def test_update(self, client: TestClient, token: str):
        assert (await client.patch(f"/{self.name}/{self.object_id}", **self.prepare_data(self.patch_data))).status_code == 401
        resp = await client.patch(
            f"/{self.name}/{self.object_id}",
            **self.prepare_data(self.patch_data),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Create patched response based on expected one and modified values only
        patch_resp = self.data.copy()
        for key, value in self.patch_data.items():
            if key in patch_resp:
                if isinstance(patch_resp[key], dict):
                    patch_resp[key].update(value)
                else:
                    patch_resp[key] = value
        assert resp.json() == patch_resp
        assert (
            await (
                client.patch(
                    f"/{self.name}/{self.object_id}",
                    **self.prepare_data(self.create_data),
                    headers={"Authorization": f"Bearer {token}"},
                )
            ).status_code
            == 200
        )

    async def test_delete(self, client: TestClient, token: str):
        assert (await client.delete(f"/{self.name}/{self.object_id}")).status_code == 401
        resp = await client.delete(f"/{self.name}/{self.object_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == self.data
        assert (
            await client.get(f"/{self.name}/{self.object_id}", headers={"Authorization": f"Bearer {token}"})
        ).status_code == 404


class TestUsers(ViewTestMixin):
    name = "users"
    create_auth = False
    tests = json_module.loads(open("tests/fixtures/data/users.json").read())


class TestDiscounts(ViewTestMixin):
    name = "discounts"
    tests = json_module.loads(open("tests/fixtures/data/discounts.json").read())

    @pytest.fixture(autouse=True)
    async def setup(self, user, client, token, anyio_backend):
        self.user = user
        await self.create_object(client, token)

    @property
    def expected_resp(self):
        data = super().expected_resp
        data["user_id"] = self.user["id"]
        return data


class TestNotifications(ViewTestMixin):
    name = "notifications"
    tests = json_module.loads(open("tests/fixtures/data/notifications.json").read())

    @pytest.fixture(autouse=True)
    async def setup(self, user, client, token, anyio_backend):
        self.user = user
        await self.create_object(client, token)

    @property
    def expected_resp(self):
        data = super().expected_resp
        data["user_id"] = self.user["id"]
        return data


class TestTemplates(ViewTestMixin):
    name = "templates"
    tests = json_module.loads(open("tests/fixtures/data/templates.json").read())

    @pytest.fixture(autouse=True)
    async def setup(self, user, client, token, anyio_backend):
        self.user = user
        await self.create_object(client, token)

    @property
    def expected_resp(self):
        data = super().expected_resp
        data["user_id"] = self.user["id"]
        return data


class TestWallets(ViewTestMixin):
    name = "wallets"
    tests = json_module.loads(open("tests/fixtures/data/wallets.json").read())


class TestStores(ViewTestMixin):
    name = "stores"
    tests = json_module.loads(open("tests/fixtures/data/stores.json").read())
    get_one_auth = False

    @pytest.fixture(autouse=True)
    async def setup(self, user, wallet, notification, client, token, anyio_backend):
        self.user = user
        self.wallet = wallet
        self.notification = notification
        await self.create_object(client, token)

    def _add_related(self, data):
        data["wallets"] = [self.wallet["id"]]
        data["notifications"] = [self.notification["id"]]

    @property
    def create_data(self):
        data = super().create_data
        self._add_related(data)
        return data

    @property
    def expected_resp(self):
        data = super().expected_resp
        self._add_related(data)
        data["user_id"] = self.user["id"]
        return data


class TestProducts(ViewTestMixin):
    name = "products"
    tests = json_module.loads(open("tests/fixtures/data/products.json").read())
    id_length = PUBLIC_ID_LENGTH
    get_one_auth = False
    json_encoding = False

    @pytest.fixture(autouse=True)
    async def setup(self, user, store, discount, client, token, anyio_backend):
        self.user = user
        self.store = store
        self.discount = discount
        await self.create_object(client, token)

    def _add_related(self, data):
        data["discounts"] = [self.discount["id"]]
        data["store_id"] = self.store["id"]

    @property
    def create_data(self):
        data = super().create_data
        self._add_related(data)
        return data

    @property
    def expected_resp(self):
        data = super().expected_resp
        self._add_related(data)
        data["user_id"] = self.user["id"]
        return data


class TestInvoices(ViewTestMixin):
    name = "invoices"
    tests = json_module.loads(open("tests/fixtures/data/invoices.json").read())
    id_length = PUBLIC_ID_LENGTH
    create_auth = False
    get_one_auth = False

    @pytest.fixture(autouse=True)
    async def setup(self, user, store, product, client, token, anyio_backend):
        self.user = user
        self.store = store
        self.product = product
        await self.create_object(client, token)

    def _add_related(self, data):
        data["products"] = [self.product["id"]]
        data["store_id"] = self.store["id"]

    @property
    def create_data(self):
        data = super().create_data
        self._add_related(data)
        return data

    @property
    def expected_resp(self):
        data = super().expected_resp
        self._add_related(data)
        data["user_id"] = self.user["id"]
        return data

    def check_data(self):
        super().check_data()
        self.check_payments()

    def check_payments(self):
        self._check_key(self.data, "payments", list)
        payments = self.data["payments"]
        assert len(payments) == 1
        method = payments[0]
        assert (
            method.items()
            > {
                "rhash": None,
                "lightning": False,
                "discount": None,
                "currency": "btc",
                "node_id": None,
                "confirmations": 0,
                "name": "BTC",
            }.items()
        )
        self.check_id(method, id_length=ID_LENGTH)
        self.check_created(method)
        for key, check_type in (
            ("payment_url", str),
            ("recommended_fee", float),
            ("amount", str),
            ("rate", str),
            ("payment_address", str),
            ("rate_str", str),
        ):
            self._check_key(method, key, check_type)
