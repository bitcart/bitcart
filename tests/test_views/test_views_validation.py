from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from bitcart.errors import BaseError as BitcartBaseError
from parametrization import Parametrization

from api import schemes
from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS, FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
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


def check_validation_failed(resp, error):
    assert resp.status_code == 422
    assert resp.json()["detail"] == error


async def test_invoice_no_wallets(client: TestClient, token, user):
    store_id = (await create_store(client, user, token, custom_store_attrs={"wallets": []}))["id"]
    check_validation_failed(
        await client.post("/invoices", json={"price": 5, "store_id": store_id}, headers={"Authorization": f"Bearer {token}"}),
        "No wallet linked",
    )


async def test_wallet_invalid_xpub(client: TestClient, token):
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


@Parametrization.autodetect_parameters()
@Parametrization.case(name="Too low transaction speed", data={"transaction_speed": -1}, error=BAD_TX_SPEED_MESSAGE)
@Parametrization.case(name="Too high transaction speed", data={"transaction_speed": 11}, error=BAD_TX_SPEED_MESSAGE)
@Parametrization.case(
    name="Too low underpaid percentage",
    data={"underpaid_percentage": -1},
    error=BAD_UNDERPAID_PERCENTAGE_MESSAGE,
)
@Parametrization.case(
    name="Too high underpaid percentage",
    data={"underpaid_percentage": 100},
    error=BAD_UNDERPAID_PERCENTAGE_MESSAGE,
)
@Parametrization.case(
    name="Too low target fee blocks",
    data={"recommended_fee_target_blocks": 0},
    error=BAD_TARGET_FEE_BLOCKS_MESSAGE,
)
@Parametrization.case(
    name="Too high target fee blocks",
    data={"recommended_fee_target_blocks": 26},
    error=BAD_TARGET_FEE_BLOCKS_MESSAGE,
)
async def test_store_checkout_settings_valid(client: TestClient, token, store, data, error):
    store_id = store["id"]
    check_validation_failed(
        await client.patch(
            f"/stores/{store_id}",
            json={"checkout_settings": data},
            headers={"Authorization": f"Bearer {token}"},
        ),
        error,
    )


async def test_invalid_notification_provider(client: TestClient, token):
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


async def test_invalid_fk_constaint(client: TestClient, token):
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


async def test_product_patch_validation_works(client: TestClient, token, product):
    product_id = product["id"]
    assert (
        await client.patch(
            f"/products/{product_id}",
            data={"data": json.dumps({"quantity": "invalid"})},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 422


@Parametrization.autodetect_parameters()
@Parametrization.case(
    name="Provider: google",
    data={"provider": "google"},
    error=BAD_BACKUP_PROVIDER_MESSAGE,
)
@Parametrization.case(
    name="Provider: Local",  # only lowercase names are allowed
    data={"provider": "Local"},
    error=BAD_BACKUP_PROVIDER_MESSAGE,
)
@Parametrization.case(
    name="Frequency: cron",  # not yet supported
    data={"frequency": "cron"},
    error=BAD_BACKUP_FREQUENCIES_MESSAGE,
)
@Parametrization.case(
    name="Frequency: yearly",  # noone uses it
    data={"frequency": "yearly"},
    error=BAD_BACKUP_FREQUENCIES_MESSAGE,
)
async def test_invalid_backup_policies(client: TestClient, token, data, error):
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
    is_eth_based = False

    async def list_fiat(self):
        raise BitcartBaseError("Doesn't work")

    async def validate_key(self, key):
        raise BitcartBaseError("Broken")


@pytest.mark.exchange_rates(cryptos={})
async def test_edge_fiatlist_cases_no_cryptos(client: TestClient, token, mocker):
    resp = await client.get("/cryptos/fiatlist")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.exchange_rates(cryptos={"btc": MockBTC()})
async def test_edge_fiatlist_cases_faulty(client: TestClient, token, mocker):
    resp = await client.get("/cryptos/fiatlist")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_edge_invoice_cases(client: TestClient, token, store, mocker, caplog):
    mocker.patch("api.crud.invoices.create_payment_method", side_effect=BitcartBaseError("Doesn't work"))
    resp = await client.post(
        "/invoices", json={"price": 5, "store_id": store["id"]}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert not data["payments"]
    assert f"Invoice {data['id']}: failed creating payment method BTC" in caplog.text


async def test_create_wallet_validate_xpub_broken(client: TestClient, mocker, token, caplog):
    mocker.patch("api.settings.settings.cryptos", {"btc": MockBTC()})
    assert (
        await client.post(
            "/wallets",
            json={"name": "brokenvalidate", "xpub": TEST_XPUB},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 422
    assert "Failed to validate xpub for currency btc" in caplog.text


async def test_access_control_strict(client: TestClient):
    user1 = await create_user(client)
    user2 = await create_user(client)
    token1 = (await create_token(client, user1))["id"]
    token2 = (await create_token(client, user2))["id"]
    # Step1: user2 can't use objects of user1 in o2m fields (i.e. store_id)
    store1 = await create_store(client, user1, token1)
    product1 = await create_product(client, user1, token1, store_id=store1["id"])
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
    # Step3: can't use other users' objects in m2m relations
    wallet_id = store1["wallets"][0]
    resp = await client.post(
        "/stores",
        json={"name": "test", "wallets": [wallet_id]},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied: attempt to use objects not owned by current user"
    # Step4: can't mark_complete invoices of another user
    invoice = await create_invoice(client, user1, token1)
    assert invoice is not None
    resp = await client.post(
        "/invoices/batch",
        json={"ids": [invoice["id"]], "command": "mark_complete"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert (await client.get(f"/invoices/{invoice['id']}")).json()["status"] == "pending"


async def test_products_invalid_json(client: TestClient, token):
    resp = await client.post(
        "/products",
        data={"data": "invalid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Invalid JSON"


async def test_payouts_invalid_destination(client: TestClient, store, wallet, token):
    resp = await client.post(
        "/payouts",
        json={"store_id": store["id"], "wallet_id": wallet["id"], "destination": "invalid", "amount": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"] == "Invalid destination address"


async def test_payouts_wallet_deleted(client: TestClient, user, token):
    payout = await create_payout(client, user["id"], token)
    assert payout["wallet_currency"] == "btc"
    wallet_id = payout["wallet_id"]
    await client.delete(f"/wallets/{wallet_id}", headers={"Authorization": f"Bearer {token}"})
    resp = await client.get(f"/payouts/{payout['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["wallet_currency"] is None


async def test_store_email_authmode_validation(client: TestClient, token, store):
    store_id = store["id"]
    check_validation_failed(
        await client.patch(
            f"/stores/{store_id}",
            json={"email_settings": {"auth_mode": "test"}},
            headers={"Authorization": f"Bearer {token}"},
        ),
        "Invalid auth_mode. Expected either of none, ssl/tls, starttls.",
    )


async def test_settings_captcha_type_validation(client: TestClient, token, store):
    check_validation_failed(
        await client.post(
            "/manage/policies",
            json={"captcha_type": "invalid"},
            headers={"Authorization": f"Bearer {token}"},
        ),
        f"Invalid captcha_type. Expected either of {', '.join(schemes.CaptchaType)}.",
    )
