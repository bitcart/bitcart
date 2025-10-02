from __future__ import annotations

import json as json_module
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

pytestmark = pytest.mark.anyio

type Metadata = dict[str, Any]


class MetadataTestMixin:
    name: str  # name used in endpoints
    tests: dict[str, Any]
    json_encoding: bool = True

    @pytest.fixture(autouse=True)
    async def setup(self, client: TestClient, token: str) -> None:
        self.client = client
        self.token = token
        self.additional_create_data: dict[str, Any] = {}

    @property
    def create_data(self) -> dict[str, Any]:
        data = self.tests["create"].copy()
        data.update(self.additional_create_data)
        return data

    def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        if self.json_encoding:
            return {"json": data}
        return {"data": {"data": json_module.dumps(data)}}

    async def create_object(self, metadata: Metadata | None = None) -> None:
        data = self.create_data
        if metadata is not None:
            data["metadata"] = metadata
        resp = await self.client.post(
            f"/{self.name}", **self.prepare_data(data), headers={"Authorization": f"Bearer {self.token}"}
        )
        assert resp.status_code == 200, resp.json()
        self.object_id = resp.json()["id"]
        self.expected_metadata = metadata or {}

    async def update_metadata(self, metadata: Metadata) -> None:
        data = {"metadata": metadata}
        resp = await self.client.patch(
            f"/{self.name}/{self.object_id}",
            **self.prepare_data(data),
            headers={"Authorization": f"Bearer {self.token}"},
        )
        assert resp.status_code == 200, resp.json()
        self.expected_metadata = metadata

    def check_pagination_response(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        assert isinstance(data["result"], list)
        return data["result"]

    async def check_get_all(self) -> None:
        resp = await self.client.get(f"/{self.name}", headers={"Authorization": f"Bearer {self.token}"})
        assert resp.status_code == 200, resp.json()
        objects = self.check_pagination_response(resp.json())
        assert "metadata" in objects[0]
        assert objects[0]["metadata"] == self.expected_metadata

    async def check_get_one(self) -> None:
        resp = await self.client.get(f"/{self.name}/{self.object_id}", headers={"Authorization": f"Bearer {self.token}"})
        assert resp.status_code == 200, resp.json()
        assert "metadata" in resp.json()
        assert resp.json()["metadata"] == self.expected_metadata

    async def check_get(self) -> None:
        await self.check_get_all()
        await self.check_get_one()

    async def test_create_with_metadata(self) -> None:
        await self.create_object({"by": "MetadataTestMixin"})
        await self.check_get()

    async def test_create_without_metadata(self) -> None:
        await self.create_object()
        await self.check_get()

    async def test_update_existing(self) -> None:
        await self.create_object({"by": "MetadataTestMixin", "version": 1})
        await self.update_metadata({"by": "MetadataTestMixin", "version": 2})
        await self.check_get()

    async def test_update_empty(self) -> None:
        await self.create_object()
        await self.update_metadata({"by": "MetadataTestMixin", "version": 2})
        await self.check_get()

    async def test_delete(self) -> None:
        await self.create_object({"by": "MetadataTestMixin"})
        await self.update_metadata({})
        await self.check_get()


def read_tests(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json_module.loads(f.read())


class TestUsers(MetadataTestMixin):
    name = "users"
    tests = read_tests("tests/fixtures/data/users.json")


class TestWallets(MetadataTestMixin):
    name = "wallets"
    tests = read_tests("tests/fixtures/data/wallets.json")


class TestNotifications(MetadataTestMixin):
    name = "notifications"
    tests = read_tests("tests/fixtures/data/notifications.json")


class TestTemplates(MetadataTestMixin):
    name = "templates"
    tests = read_tests("tests/fixtures/data/templates.json")


class TestStores(MetadataTestMixin):
    name = "stores"
    tests = read_tests("tests/fixtures/data/stores.json")

    @pytest.fixture(autouse=True)
    async def setup(self, client: TestClient, token: str, wallet: dict[str, Any], notification: dict[str, Any]) -> None:
        self.client = client
        self.token = token
        self.additional_create_data = {"wallets": [wallet["id"]], "notifications": [notification["id"]]}


class TestDiscounts(MetadataTestMixin):
    name = "discounts"
    tests = read_tests("tests/fixtures/data/discounts.json")


class TestProducts(MetadataTestMixin):
    name = "products"
    tests = read_tests("tests/fixtures/data/products.json")
    json_encoding = False

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        client: TestClient,
        token: str,
        store: dict[str, Any],
        discount: dict[str, Any],
    ) -> None:
        self.client = client
        self.token = token
        self.additional_create_data = {"discounts": [discount["id"]], "store_id": store["id"]}


class TestInvoices(MetadataTestMixin):
    name = "invoices"
    tests = read_tests("tests/fixtures/data/invoices.json")

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        client: TestClient,
        token: str,
        store: dict[str, Any],
        product: dict[str, Any],
    ) -> None:
        self.client = client
        self.token = token
        self.additional_create_data = {"products": [product["id"]], "store_id": store["id"]}


class TestPayouts(MetadataTestMixin):
    name = "payouts"
    tests = read_tests("tests/fixtures/data/payouts.json")

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        client: TestClient,
        token: str,
        store: dict[str, Any],
        wallet: dict[str, Any],
    ) -> None:
        self.client = client
        self.token = token
        self.additional_create_data = {"store_id": store["id"], "wallet_id": wallet["id"]}
