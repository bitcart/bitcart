from __future__ import annotations

import json as json_module
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest

from api.constants import ID_LENGTH

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient


pytestmark = pytest.mark.anyio


def assert_contains(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    missing = set(expected) - set(actual)
    if missing:
        raise AssertionError(f"Missing keys: {sorted(missing)}")
    mismatched = {k: (expected[k], actual[k]) for k in expected if actual[k] != expected[k]}
    if mismatched:
        msgs = [f"{k!r}: expected {exp!r}, got {got!r}" for k, (exp, got) in mismatched.items()]
        raise AssertionError("Mismatches:\n  " + "\n  ".join(msgs))


class ViewTestMixin:
    """Base class for all modelview tests, as they mostly don't differ

    You must set some parameters unset in this class for it to work in your subclass
    """

    name: str  # name used in endpoints
    create_auth: bool = True
    get_one_auth: bool = True
    id_length: int = ID_LENGTH
    json_encoding: bool = True

    tests: dict[str, Any]

    computed_fields = {"updated"}

    @pytest.fixture
    def state(self) -> dict[str, Any]:
        return {}

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        state["data"] = await self.create_object(client, token, state)
        if self.name == "users":
            token = state["data"].pop("token", None)
            assert token is not None
            assert (await client.delete(f"/token/{token}", headers={"Authorization": f"Bearer {token}"})).status_code == 200

    @pytest.fixture
    def object_id(self, state: dict[str, Any]) -> str:
        return state["data"]["id"]

    def create_data(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.tests["create"]

    @property
    def patch_data(self) -> dict[str, Any]:
        return self.tests["patch"]

    def expected_resp(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.tests["response"]

    @property
    def expected_count(self) -> int:
        return self.tests["count"]

    async def create_object(self, client: TestClient, token: str, state: dict[str, Any]) -> dict[str, Any]:
        # Create initial object for other tests
        if self.create_auth:
            assert (await client.post(f"/{self.name}", **self.prepare_data(self.create_data(state)))).status_code == 401
        resp = await client.post(
            f"/{self.name}", **self.prepare_data(self.create_data(state)), headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, resp.json()
        return resp.json()

    def check_pagination_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        assert data["count"] == self.expected_count
        assert not data["previous"]
        assert not data["next"]
        assert isinstance(data["result"], list)
        return data["result"]

    def _check_key(self, data: dict[str, Any], key: str, key_type: type) -> None:
        assert key in data
        assert isinstance(data[key], key_type)

    def check_id(self, data: dict[str, Any], id_length: int) -> None:
        self._check_key(data, "id", str)
        assert len(data["id"]) == id_length

    def check_created(self, data: dict[str, Any]) -> None:
        self._check_key(data, "created", str)
        try:
            datetime.fromisoformat(data["created"])
        except ValueError:
            pytest.fail(f"Invalid created field: {data['created']}")

    def check_data(self, data: dict[str, Any]) -> None:
        self.check_id(data, id_length=self.id_length)
        self.check_created(data)

    # The actual create is done by data fixture once
    async def test_create(self, state: dict[str, Any]) -> None:
        assert_contains(self.expected_resp(state), state["data"])
        self.check_data(state["data"])

    def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.json_encoding:
            return {"json": data}
        return {"data": {"data": json_module.dumps(data)}}

    async def test_get_all(self, client: TestClient, token: str, state: dict[str, Any]) -> None:
        assert (await client.get(f"/{self.name}")).status_code == 401
        resp = await client.get(f"/{self.name}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        objects = self.check_pagination_response(resp.json())
        # The objects list is ordered by created date; first object is the last object created
        assert objects[0] == state["data"]

    async def test_get_count(self, client: TestClient, token: str) -> None:
        assert (await client.get(f"/{self.name}/count")).status_code == 401
        resp = await client.get(f"/{self.name}/count", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == self.expected_count

    async def test_get_one(self, client: TestClient, token: str, state: dict[str, Any], object_id: str) -> None:
        if self.get_one_auth:
            assert (await client.get(f"/{self.name}/{object_id}")).status_code == 401
        resp = await client.get(f"/{self.name}/{object_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == state["data"]

    def get_computed_fields(self) -> set[str]:
        return getattr(self, "computed_fields", set())

    async def test_update(self, client: TestClient, token: str, state: dict[str, Any], object_id: str) -> None:
        assert (await client.patch(f"/{self.name}/{object_id}", **self.prepare_data(self.patch_data))).status_code == 401
        resp = await client.patch(
            f"/{self.name}/{object_id}",
            **self.prepare_data(self.patch_data),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        # Create patched response based on expected one and modified values only
        patch_resp = state["data"].copy()
        for key, value in self.patch_data.items():
            if key in patch_resp:
                if isinstance(patch_resp[key], dict):
                    patch_resp[key].update(value)
                else:
                    patch_resp[key] = value
        patch_resp["updated"] = resp.json()["updated"]

        computed_fields = self.get_computed_fields()
        for field in computed_fields:
            if field in resp.json():
                patch_resp[field] = resp.json()[field]

        assert resp.json() == patch_resp
        assert (
            await client.patch(
                f"/{self.name}/{object_id}",
                **self.prepare_data(self.create_data(state)),
                headers={"Authorization": f"Bearer {token}"},
            )
        ).status_code == 200

    async def test_delete(self, client: TestClient, token: str, state: dict[str, Any], object_id: str) -> None:
        assert (await client.delete(f"/{self.name}/{object_id}")).status_code == 401
        resp = await client.delete(f"/{self.name}/{object_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == state["data"]
        assert (await client.get(f"/{self.name}/{object_id}", headers={"Authorization": f"Bearer {token}"})).status_code == 404


def read_tests(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json_module.loads(f.read())


class TestUsers(ViewTestMixin):
    name = "users"
    create_auth = False
    tests = read_tests("tests/fixtures/data/users.json")
    computed_fields = {"totp_url"}.union(ViewTestMixin.computed_fields)


class TestWallets(ViewTestMixin):
    name = "wallets"
    tests = read_tests("tests/fixtures/data/wallets.json")


class TestNotifications(ViewTestMixin):
    name = "notifications"
    tests = read_tests("tests/fixtures/data/notifications.json")

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        user: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        state["user"] = user
        state["data"] = await self.create_object(client, token, state)


class TestTemplates(ViewTestMixin):
    name = "templates"
    tests = read_tests("tests/fixtures/data/templates.json")

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        user: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        state["user"] = user
        state["data"] = await self.create_object(client, token, state)


class TestStores(ViewTestMixin):
    name = "stores"
    tests = read_tests("tests/fixtures/data/stores.json")
    get_one_auth = False

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        user: dict[str, Any],
        wallet: dict[str, Any],
        notification: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        state["user"] = user
        state["wallet"] = wallet
        state["notification"] = notification
        state["data"] = await self.create_object(client, token, state)

    def _add_related(self, data: dict[str, Any], state: dict[str, Any]) -> None:
        data["wallets"] = [state["wallet"]["id"]]
        data["notifications"] = [state["notification"]["id"]]

    def create_data(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().create_data(state)
        self._add_related(data, state)
        return data

    def expected_resp(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().expected_resp(state)
        self._add_related(data, state)
        return data


class TestDiscounts(ViewTestMixin):
    name = "discounts"
    tests = read_tests("tests/fixtures/data/discounts.json")

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        user: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        state["user"] = user
        state["data"] = await self.create_object(client, token, state)


class TestProducts(ViewTestMixin):
    name = "products"
    tests = read_tests("tests/fixtures/data/products.json")
    get_one_auth = False
    json_encoding = False

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        user: dict[str, Any],
        store: dict[str, Any],
        discount: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        state["user"] = user
        state["store"] = store
        state["discount"] = discount
        state["data"] = await self.create_object(client, token, state)

    def _add_related(self, data: dict[str, Any], state: dict[str, Any]) -> None:
        data["discounts"] = [state["discount"]["id"]]
        data["store_id"] = state["store"]["id"]

    def create_data(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().create_data(state)
        self._add_related(data, state)
        return data

    def expected_resp(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().expected_resp(state)
        self._add_related(data, state)
        return data


class TestInvoices(ViewTestMixin):
    name = "invoices"
    tests = read_tests("tests/fixtures/data/invoices.json")
    create_auth = False
    get_one_auth = False

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        user: dict[str, Any],
        store: dict[str, Any],
        product: dict[str, Any],
    ) -> None:
        state["user"] = user
        state["store"] = store
        state["product"] = product
        state["data"] = await self.create_object(client, token, state)

    def _add_related(self, data: dict[str, Any], state: dict[str, Any]) -> None:
        data["products"] = [state["product"]["id"]]
        data["store_id"] = state["store"]["id"]

    def create_data(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().create_data(state)
        self._add_related(data, state)
        return data

    def expected_resp(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().expected_resp(state)
        self._add_related(data, state)
        return data

    def check_data(self, data: dict[str, Any]) -> None:
        super().check_data(data)
        self.check_payments(data)

    def check_payments(self, data: dict[str, Any]) -> None:
        self._check_key(data, "payments", list)
        payments = data["payments"]
        assert len(payments) == 1
        method = payments[0]
        assert_contains(
            {
                "rhash": None,
                "lightning": False,
                "discount": None,
                "currency": "btc",
                "node_id": None,
                "confirmations": 0,
                "name": "BTC",
            },
            method,
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


class TestPayouts(ViewTestMixin):
    name = "payouts"
    tests = read_tests("tests/fixtures/data/payouts.json")

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        state: dict[str, Any],
        client: TestClient,
        token: str,
        anyio_backend: tuple[str, dict[str, Any]],
        user: dict[str, Any],
        store: dict[str, Any],
        wallet: dict[str, Any],
    ) -> None:
        state["user"] = user
        state["store"] = store
        state["wallet"] = wallet
        state["data"] = await self.create_object(client, token, state)

    def _add_related(self, data: dict[str, Any], state: dict[str, Any]) -> None:
        data["store_id"] = state["store"]["id"]
        data["wallet_id"] = state["wallet"]["id"]

    def create_data(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().create_data(state)
        self._add_related(data, state)
        return data

    def expected_resp(self, state: dict[str, Any]) -> dict[str, Any]:
        data = super().expected_resp(state)
        self._add_related(data, state)
        return data
