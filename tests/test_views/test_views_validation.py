import json

from parametrization import Parametrization
from starlette.testclient import TestClient

from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS, FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
from tests.fixtures.static_data import TEST_XPUB
from tests.helper import create_store

BAD_TX_SPEED_MESSAGE = f"Transaction speed must be in range from 0 to {MAX_CONFIRMATION_WATCH}"
BAD_UNDERPAID_PERCENTAGE_MESSAGE = "Underpaid percentage must be in range from 0 to 99.99"
BAD_TARGET_FEE_BLOCKS_MESSAGE = (
    f"Recommended fee confirmation target blocks must be either of: {', '.join(map(str, FEE_ETA_TARGETS))}"
)
BAD_BACKUP_PROVIDER_MESSAGE = f"Backup provider must be either of: {', '.join(map(str, BACKUP_PROVIDERS))}"
BAD_BACKUP_FREQUENCIES_MESSAGE = f"Backup frequency must be either of: {', '.join(map(str, BACKUP_FREQUENCIES))}"


def check_validation_failed(resp, error):
    assert resp.status_code == 422
    assert resp.json()["detail"] == error


def test_invoice_no_wallets(client: TestClient, token, user):
    store_id = create_store(client, user, token, custom_store_attrs={"wallets": []})["id"]
    check_validation_failed(
        client.post("/invoices", json={"price": 5, "store_id": store_id}, headers={"Authorization": f"Bearer {token}"}),
        "No wallet linked",
    )


def test_wallet_invalid_xpub(client: TestClient, token):
    # Unable to create invalid wallet
    check_validation_failed(
        client.post("/wallets", json={"name": "test", "xpub": "invalid"}, headers={"Authorization": f"Bearer {token}"}),
        "Wallet key invalid",
    )
    resp = client.post("/wallets", json={"name": "test", "xpub": TEST_XPUB}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    wallet_id = resp.json()["id"]
    # Unable to break existing wallet
    check_validation_failed(
        client.patch(f"/wallets/{wallet_id}", json={"xpub": "invalid"}, headers={"Authorization": f"Bearer {token}"}),
        "Wallet key invalid",
    )


@Parametrization.autodetect_parameters()
@Parametrization.case(name="Too low transaction speed", data={"transaction_speed": -1}, error=BAD_TX_SPEED_MESSAGE)
@Parametrization.case(name="Too high transaction speed", data={"transaction_speed": 7}, error=BAD_TX_SPEED_MESSAGE)
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
def test_store_checkout_settings_valid(client: TestClient, token, store, data, error):
    store_id = store["id"]
    check_validation_failed(
        client.patch(
            f"/stores/{store_id}",
            json={"checkout_settings": data},
            headers={"Authorization": f"Bearer {token}"},
        ),
        error,
    )


def test_invalid_notification_provider(client: TestClient, token):
    # Only allow providers supported by the notifiers library to prevent further errors
    check_validation_failed(
        client.post(
            "/notifications",
            json={"name": "test", "provider": "invalid", "data": {}},
            headers={"Authorization": f"Bearer {token}"},
        ),
        "Unsupported notificaton provider",
    )
    assert (
        client.post(
            "/notifications",
            json={"name": "test", "provider": "telegram", "data": {}},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 200
    )


def test_invalid_fk_constaint(client: TestClient, token):
    # For m2m, it disallows invalid foreign keys with a bit different error
    resp = client.post("/stores", json={"name": "test", "wallets": [999]}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Access denied: attempt to use objects not owned by current user"
    # For invoices (custom logic), it returns 404 at initial store fetching stage
    assert (
        client.post("/invoices", json={"price": 5, "store_id": 999}, headers={"Authorization": f"Bearer {token}"}).status_code
        == 404
    )
    # For others, the database should verify fk integrity
    resp = client.post(
        "/products",
        data={"data": json.dumps({"name": "test", "price": 1, "quantity": 1, "store_id": 999})},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert "violates foreign key constraint" in resp.json()["detail"]


def test_product_patch_validation_works(client: TestClient, token, product):
    product_id = product["id"]
    assert (
        client.patch(
            f"/products/{product_id}",
            data={"data": json.dumps({"quantity": "invalid"})},
            headers={"Authorization": f"Bearer {token}"},
        ).status_code
        == 422
    )


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
def test_invalid_backup_policies(client: TestClient, token, data, error):
    check_validation_failed(
        client.post(
            "/manage/backups",
            json=data,
            headers={"Authorization": f"Bearer {token}"},
        ),
        error,
    )
