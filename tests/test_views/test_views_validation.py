from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import pytest_mock
from bitcart.errors import BaseError as BitcartBaseError

from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS, FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
from api.schemas.misc import CaptchaType
from tests.fixtures.static_data import TEST_XPUB
from tests.helper import create_invoice, create_payout, create_product, create_store, create_token, create_user

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

BAD_TX_SPEED_MESSAGE = f"Transaction speed must be in range from 0 to {MAX_CONFIRMATION_WATCH}"
BAD_UNDERPAID_PERCENTAGE_MESSAGE = "Underpaid percentage must be in range from 0 to 99.99"
BAD_TARGET_FEE_BLOCKS_MESSAGE = (
    f"Recommended fee confirmation target blocks must be either of: {', '.join(map(str, FEE_ETA_TARGETS))}"
)
BAD_BACKUP_PROVIDER_MESSAGE = f"Backup provider must be either of: {', '.join(map(str, BACKUP_PROVIDERS))}"
BAD_BACKUP_FREQUENCIES_MESSAGE = f"Backup frequency must be either of: {', '.join(map(str, BACKUP_FREQUENCIES))}"

pytestmark = pytest.mark.anyio


def check_validation_failed(resp: httpx.Response, error: str) -> None:
    assert resp.status_code == 422
    assert resp.json()["detail"] == error


async def test_invoice_no_wallets(client: TestClient, token: str) -> None:
    store_id = (await create_store(client, token, custom_store_attrs={"wallets": []}))["id"]
    check_validation_failed(
        await client.post("/invoices", json={"price": 5, "store_id": store_id}, headers={"Authorization": f"Bearer {token}"}),
        "No wallet linked",
    )


async def test_wallet_invalid_xpub(client: TestClient, token: str) -> None:
    # Unable to create invalid wallet
    check_validation_failed(
        await client.post("/wallets", json={"name": "test", "xpub": "invalid"}, headers={"Authorization": f"Bearer {token}"}),
        "Wallet key invalid",
    )
    resp = await client.post(
        "/wallets", json={"name": "test", "xpub": TEST_XPUB}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    wallet_id = resp.json()["id"]
    # Unable to break existing wallet
    check_validation_failed(
        await client.patch(f"/wallets/{wallet_id}", json={"xpub": "invalid"}, headers={"Authorization": f"Bearer {token}"}),
        "Wallet key invalid",
    )


@pytest.mark.parametrize(
    "transaction_speed",
    [
        pytest.param(-1, id="Too low transaction speed"),
        pytest.param(201, id="Too high transaction speed"),
    ],
)
async def test_wallet_transaction_speed_validation(client: TestClient, token: str, transaction_speed: int) -> None:
    check_validation_failed(
        await client.post(
            "/wallets",
            json={"name": "test", "xpub": TEST_XPUB, "transaction_speed": transaction_speed},
            headers={"Authorization": f"Bearer {token}"},
        ),
        BAD_TX_SPEED_MESSAGE,
    )


@pytest.mark.parametrize(
    "data,error",
    [
        pytest.param({"transaction_speed": -1}, BAD_TX_SPEED_MESSAGE, id="Too low transaction speed"),
        pytest.param({"transaction_speed": 201}, BAD_TX_SPEED_MESSAGE, id="Too high transaction speed"),
        pytest.param({"underpaid_percentage": -1}, BAD_UNDERPAID_PERCENTAGE_MESSAGE, id="Too low underpaid percentage"),
        pytest.param({"underpaid_percentage": 100}, BAD_UNDERPAID_PERCENTAGE_MESSAGE, id="Too high underpaid percentage"),
        pytest.param({"recommended_fee_target_blocks": 0}, BAD_TARGET_FEE_BLOCKS_MESSAGE, id="Too low target fee blocks"),
        pytest.param({"recommended_fee_target_blocks": 26}, BAD_TARGET_FEE_BLOCKS_MESSAGE, id="Too high target fee blocks"),
    ],
)
async def test_store_checkout_settings_valid(
    client: TestClient, token: str, store: dict[str, Any], data: dict[str, Any], error: str
) -> None:
    store_id = store["id"]
    check_validation_failed(
        await client.patch(
            f"/stores/{store_id}",
            json={"checkout_settings": data},
            headers={"Authorization": f"Bearer {token}"},
        ),
        error,
    )


async def test_invalid_notification_provider(client: TestClient, token: str) -> None:
    # Only allow providers supported by the notifiers library to prevent further errors
    resp = await client.post(
        "/notifications",
        json={"name": "test", "provider": "invalid", "data": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["error"]
    assert (
        await client.post(
            "/notifications",
            json={"name": "test", "provider": "Telegram", "data": {}},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200


async def test_invalid_fk_constaint(client: TestClient, token: str) -> None:
    # For m2m, it disallows invalid foreign keys with a bit different error
    resp = await client.post(
        "/stores", json={"name": "test", "wallets": ["999"]}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied: attempt to use objects not owned by current user"
    # For invoices (custom logic), it returns 404 at initial store fetching stage
    assert (
        await client.post("/invoices", json={"price": 5, "store_id": "999"}, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404
    # For o2m keys it should do the same
    resp = await client.post(
        "/products",
        data={"data": json.dumps({"name": "test", "price": 1, "quantity": 1, "store_id": "999"})},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied: attempt to use objects not owned by current user"


async def test_product_patch_validation_works(client: TestClient, token: str, product: dict[str, Any]) -> None:
    product_id = product["id"]
    assert (
        await client.patch(
            f"/products/{product_id}",
            data={"data": json.dumps({"quantity": "invalid"})},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 422


@pytest.mark.parametrize(
    "data,error",
    [
        pytest.param({"provider": "google"}, BAD_BACKUP_PROVIDER_MESSAGE, id="Provider: google"),
        pytest.param({"provider": "Local"}, BAD_BACKUP_PROVIDER_MESSAGE, id="Provider: Local"),
        pytest.param({"frequency": "cron"}, BAD_BACKUP_FREQUENCIES_MESSAGE, id="Frequency: cron"),
        pytest.param({"frequency": "yearly"}, BAD_BACKUP_FREQUENCIES_MESSAGE, id="Frequency: yearly"),
    ],
)
async def test_invalid_backup_policies(client: TestClient, token: str, data: dict[str, Any], error: str) -> None:
    check_validation_failed(
        await client.post(
            "/manage/backups",
            json=data,
            headers={"Authorization": f"Bearer {token}"},
        ),
        error,
    )


class MockBTC:
    coin_name = "BTC"
    friendly_name = "Bitcoin"
    is_eth_based = False

    async def list_fiat(self) -> list[str]:
        raise BitcartBaseError("Doesn't work")

    async def validate_key(self, key: str) -> bool:
        raise BitcartBaseError("Broken")


@pytest.mark.exchange_rates(cryptos={})
async def test_edge_fiatlist_cases_no_cryptos(client: TestClient, token: str, mocker: pytest_mock.MockerFixture) -> None:
    resp = await client.get("/cryptos/fiatlist")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.exchange_rates(cryptos={"btc": MockBTC()})
async def test_edge_fiatlist_cases_faulty(client: TestClient, token: str, mocker: pytest_mock.MockerFixture) -> None:
    resp = await client.get("/cryptos/fiatlist")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_edge_invoice_cases(
    client: TestClient, token: str, store: dict[str, Any], mocker: pytest_mock.MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    mocker.patch(
        "api.services.crud.invoices.InvoiceService.create_payment_method", side_effect=BitcartBaseError("Doesn't work")
    )
    resp = await client.post(
        "/invoices", json={"price": 5, "store_id": store["id"]}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert not data["payments"]
    assert f"Invoice {data['id']}: failed creating payment method BTC" in caplog.text


@pytest.mark.exchange_rates(cryptos={"btc": MockBTC()})
async def test_create_wallet_validate_xpub_broken(
    client: TestClient, mocker: pytest_mock.MockerFixture, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    assert (
        await client.post(
            "/wallets",
            json={"name": "brokenvalidate", "xpub": TEST_XPUB},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 422
    assert "Failed to validate xpub for currency btc" in caplog.text


async def test_access_control_strict(client: TestClient) -> None:
    user1 = await create_user(client)
    token1 = (await create_token(client, user1))["id"]
    user2 = await create_user(client, token=token1)
    token2 = (await create_token(client, user2))["id"]
    # Step1: user2 can't use objects of user1 in o2m fields (i.e. store_id)
    store1 = await create_store(client, token1)
    product1 = await create_product(client, token1, store_id=store1["id"])
    assert product1 is not None
    resp = await client.post(
        "/products",
        data={"data": json.dumps({"name": "test", "price": 1, "quantity": 1, "store_id": store1["id"]})},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied: attempt to use objects not owned by current user"
    # Step2: can't modify user_id of objects
    resp = await client.patch(
        f"/products/{product1['id']}",
        data={"data": json.dumps({"user_id": user2["id"]})},
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.json()["user_id"] == user1["id"]
    # # Step3: can't use other users' objects in m2m relations
    wallet_id = store1["wallets"][0]
    resp = await client.post(
        "/stores",
        json={"name": "test", "wallets": [wallet_id]},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied: attempt to use objects not owned by current user"
    # Step4: can't mark_complete invoices of another user
    invoice = await create_invoice(client, token1)
    assert invoice is not None
    resp = await client.post(
        "/invoices/batch",
        json={"ids": [invoice["id"]], "command": "mark_complete"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert (await client.get(f"/invoices/{invoice['id']}")).json()["status"] == "pending"


async def test_products_invalid_json(client: TestClient, token: str) -> None:
    resp = await client.post(
        "/products",
        data={"data": "invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Invalid JSON"


async def test_payouts_invalid_destination(
    client: TestClient, store: dict[str, Any], wallet: dict[str, Any], token: str
) -> None:
    resp = await client.post(
        "/payouts",
        json={"store_id": store["id"], "wallet_id": wallet["id"], "destination": "invalid", "amount": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Invalid destination address"


async def test_payouts_wallet_deleted(client: TestClient, token: str) -> None:
    payout = await create_payout(client, token)
    assert payout["wallet_currency"] == "btc"
    wallet_id = payout["wallet_id"]
    assert (await client.delete(f"/wallets/{wallet_id}", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    resp = await client.get(f"/payouts/{payout['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["wallet_currency"] is None


async def test_store_email_authmode_validation(client: TestClient, token: str, store: dict[str, Any]) -> None:
    store_id = store["id"]
    check_validation_failed(
        await client.patch(
            f"/stores/{store_id}",
            json={"email_settings": {"auth_mode": "test"}},
            headers={"Authorization": f"Bearer {token}"},
        ),
        "Invalid auth_mode. Expected either of none, ssl/tls, starttls.",
    )


async def test_settings_captcha_type_validation(client: TestClient, token: str, store: dict[str, Any]) -> None:
    check_validation_failed(
        await client.post(
            "/manage/policies",
            json={"captcha_type": "invalid"},
            headers={"Authorization": f"Bearer {token}"},
        ),
        f"Invalid captcha_type. Expected either of {', '.join(CaptchaType)}.",
    )
