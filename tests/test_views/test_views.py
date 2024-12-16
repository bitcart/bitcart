from __future__ import annotations

import asyncio
import json as json_module
import os
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

import pyotp
import pytest
from bitcart import BTC, LTC
from bitcart.errors import BaseError as BitcartBaseError
from httpx_ws import WebSocketDisconnect, aconnect_ws
from parametrization import Parametrization
from starlette.status import WS_1008_POLICY_VIOLATION

from api import invoices, models, schemes, settings, utils
from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS, DOCKER_REPO_URL, SUPPORTED_CRYPTOS
from api.ext import payouts
from api.ext import tor as tor_ext
from api.invoices import InvoiceStatus
from tests.fixtures import static_data
from tests.helper import create_invoice, create_product, create_store, create_token, create_user, create_wallet, enabled_logs

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

pytestmark = pytest.mark.anyio


class DummyInstance:
    coin_name = "BTC"


async def test_docs_root(client: TestClient):
    response = await client.get("/")
    assert response.status_code == 200


async def test_rate(client: TestClient):
    resp = await client.get("/cryptos/rate")
    data = resp.json()
    assert resp.status_code == 200
    assert isinstance(data, int | float)
    assert data > 0
    assert (await client.get("/cryptos/rate?fiat_currency=eur")).status_code == 200
    assert (await client.get("/cryptos/rate?fiat_currency=EUR")).status_code == 200
    assert (await client.get("/cryptos/rate?fiat_currency=test")).status_code == 422


async def test_wallet_rate(client: TestClient, token: str, wallet):
    resp = await client.get(f"/wallets/{wallet['id']}/rate")
    data = resp.json()
    assert resp.status_code == 200
    assert isinstance(data, int | float)
    assert data > 0
    assert (await client.get(f"/wallets/{wallet['id']}/rate?currency=eur")).status_code == 200
    assert (await client.get(f"/wallets/{wallet['id']}/rate?currency=EUR")).status_code == 200
    assert (await client.get(f"/wallets/{wallet['id']}/rate?currency=test")).status_code == 422


async def test_wallet_history(client: TestClient, token: str, wallet):
    assert (await client.get("/wallets/history/999")).status_code == 401
    assert (await client.get("/wallets/history/all")).status_code == 401
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/wallets/history/999", headers=headers)).status_code == 404
    resp1 = await client.get(f"/wallets/history/{wallet['id']}", headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) == 1
    assert data1[0]["amount"] == "0.01"
    assert data1[0]["txid"] == "ee4f0c4405f9ba10443958f5c6f6d4552a69a80f3ec3bed1c3d4c98d65abe8f3"
    resp2 = await client.get("/wallets/history/all", headers=headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data1 == data2


@Parametrization.autodetect_parameters()
@Parametrization.case(name="exist-user-correct-pwd", user_exists=True, correct_pwd=True)
@Parametrization.case(name="exist-user-wrong-pwd", user_exists=True, correct_pwd=False)
@Parametrization.case(name="non-exist-user", user_exists=False, correct_pwd=False)
async def test_create_token(client: TestClient, user, user_exists: bool, correct_pwd: bool):
    email = user["email"] if user_exists else "non-exist@example.com"
    password = static_data.USER_PWD if (user_exists and correct_pwd) else "wrong-password"
    resp = await client.post("/token", json={"email": email, "password": password})
    if user_exists and correct_pwd:
        assert resp.status_code == 200
        j = resp.json()
        assert j.get("access_token")
        assert j["token_type"] == "bearer"
    else:
        assert resp.status_code == 401


async def test_noauth(client: TestClient):
    assert (await client.get("/users")).status_code == 401
    assert (await client.get("/wallets")).status_code == 401
    assert (await client.get("/stores")).status_code == 401
    assert (await client.get("/products")).status_code == 401
    assert (await client.get("/invoices")).status_code == 401
    assert (
        await client.post("/discounts", json={"name": "test_no_auth", "percent": 20, "end_date": "2020-01-01 21:19:34.503627"})
    ).status_code == 401
    assert (await client.get("/products?&store=2")).status_code == 200


async def test_superuseronly(client: TestClient, token: str, limited_token: str):
    assert (await client.get("/users", headers={"Authorization": f"Bearer {limited_token}"})).status_code == 403
    assert (await client.get("/users", headers={"Authorization": f"Bearer {token}"})).status_code == 200


async def test_users_me(client: TestClient, user, token: str):
    assert (await client.get("/users/me")).status_code == 401
    resp = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    j = resp.json()
    assert j.items() > {"is_superuser": True, "email": user["email"]}.items()
    assert "created" in j


async def test_wallets_balance(client: TestClient, token: str, wallet):
    assert (await client.get("/wallets/balance")).status_code == 401
    resp = await client.get("/wallets/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert Decimal(resp.json()) > 1


async def test_fiatlist(client: TestClient):
    resp = await client.get("/cryptos/fiatlist")
    assert resp.status_code == 200
    j1 = resp.json()
    assert isinstance(j1, list)
    assert "BTC" in j1
    assert "USD" in j1
    resp2 = await client.get("/cryptos/fiatlist?query=b")
    assert resp2.status_code == 200
    j2 = resp2.json()
    assert isinstance(j2, list)
    assert "BTC" in j2
    resp3 = await client.get("/cryptos/fiatlist?query=U")
    assert resp3.status_code == 200
    j3 = resp3.json()
    assert isinstance(j3, list)
    assert "USD" in j3


async def test_fiatlist_multi_coins(client: TestClient, mocker):
    mocker.patch.object(settings.settings, "cryptos", {"btc": BTC(), "ltc": LTC()})
    resp = await client.get("/cryptos/fiatlist")
    assert len(resp.json()) > 30


async def check_ws_response(ws, sent_amount):
    data = await ws.receive_json()
    assert (
        data.items()
        >= {"status": "paid", "exception_status": "none", "sent_amount": sent_amount, "paid_currency": "BTC"}.items()
    )
    assert data["payment_id"] is not None
    data = await ws.receive_json()
    assert (
        data.items()
        >= {"status": "complete", "exception_status": "none", "sent_amount": sent_amount, "paid_currency": "BTC"}.items()
    )
    assert data["payment_id"] is not None


async def check_ws_response_complete(ws, sent_amount):
    data = await ws.receive_json()
    assert (
        data.items()
        >= {"status": "complete", "exception_status": "none", "sent_amount": sent_amount, "paid_currency": "BTC"}.items()
    )
    assert data["payment_id"] is not None


async def check_ws_response2(ws):
    data = await ws.receive_json()
    assert data == {"status": "success", "balance": "0.01"}


@Parametrization.autodetect_parameters()
@Parametrization.case(name="non-exist-store-unauthorized", store_exists=True, authorized=False)
@Parametrization.case(name="non-exist-store-authorized", store_exists=False, authorized=True)
@Parametrization.case(name="store-unauthorized", store_exists=True, authorized=False)
@Parametrization.case(name="store-authorized", store_exists=True, authorized=True)
async def test_ping_email(client: TestClient, token: str, store, store_exists, authorized):
    store_id = store["id"] if store_exists else 999
    resp = await client.get(f"/stores/{store_id}/ping", headers={"Authorization": f"Bearer {token}"} if authorized else {})
    if authorized:
        if store_exists:
            assert resp.status_code == 200
            assert not resp.json()
        else:
            assert resp.status_code == 404
    else:
        assert resp.status_code == 401


async def test_user_stats(client, user, token, store):
    store_id = store["id"]
    await create_product(client, user["id"], token, store_id=store_id)
    await create_invoice(client, user["id"], token, store_id=store_id)
    await create_invoice(client, user["id"], token, store_id=store_id)
    resp = await client.get("/users/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert (
        data.items()
        > {
            "discounts": 0,
            "invoices": 2,
            "notifications": 0,
            "products": 1,
            "stores": 1,
            "templates": 0,
            "wallets": 1,
        }.items()
    )


@Parametrization.autodetect_parameters()
@Parametrization.case(name="single", categories=["all"])
@Parametrization.case(name="multiple", categories=["all", "test"])
async def test_categories(client: TestClient, user, token, categories: list, store):
    assert (await client.get("/products/categories")).status_code == 422
    store_id = store["id"]
    # all category is there always
    assert (await client.get(f"/products/categories?store={store_id}")).json() == ["all"]
    for category in categories:
        await create_product(client, user["id"], token, store_id=store_id, category=category)
    resp = await client.get(f"/products/categories?store={store_id}")
    assert resp.status_code == 200
    assert resp.json() == categories


async def test_token(client: TestClient, token_data):
    assert (await client.get("/token")).status_code == 401
    resp = await client.get("/token", headers={"Authorization": f"Bearer {token_data['id']}"})
    assert resp.status_code == 200
    j = resp.json()
    assert j["count"] == 1
    assert not j["previous"]
    assert not j["next"]
    result = j["result"]
    assert isinstance(result, list)
    assert len(result) == 1
    result = result[0]
    assert {
        "app_id": token_data["app_id"],
        "permissions": token_data["permissions"],
        "user_id": token_data["user_id"],
        "redirect_url": token_data["redirect_url"],
    }.items() <= result.items()


async def test_token_current(client: TestClient, token: str, user):
    assert (await client.get("/token/current")).status_code == 401
    resp = await client.get("/token/current", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    j = resp.json()
    assert isinstance(j, dict)
    assert j["user_id"] == user["id"]
    assert j["app_id"] == ""
    assert j["redirect_url"] == ""
    assert j["permissions"] == ["full_control"]
    assert j["id"] == token


async def test_token_count(client: TestClient, token: str):
    assert (await client.get("/token/count")).status_code == 401
    resp = await client.get("/token/count", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == 1


async def test_patch_token(client: TestClient, token):
    assert (await client.patch(f"/token/{token}", json={"redirect_url": "google.com:443"})).status_code == 401
    resp = await client.patch(
        f"/token/{token}",
        json={"redirect_url": "google.com:443"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    j = resp.json()
    assert j["redirect_url"] == "google.com:443"
    assert j["id"] == token


@Parametrization.autodetect_parameters()
@Parametrization.case(name="non-user-unauthorized", user_exists=False, authorized=False)
@Parametrization.case(name="non-user-authorized", user_exists=False, authorized=True)
@Parametrization.case(name="user-unauthorized", user_exists=True, authorized=False)
@Parametrization.case(name="user-authorized", user_exists=True, authorized=True)
async def test_create_tokens(client: TestClient, user, token: str, user_exists: bool, authorized: bool):
    password = static_data.USER_PWD
    email = user["email"] if user_exists else f"NULL{user['email']}"
    resp = await client.post(
        "/token",
        json={"email": email, "password": password},
        headers={"Authorization": f"Bearer {token}"} if authorized else {},
    )
    if authorized:
        assert resp.status_code == 200
    else:
        if user_exists:
            assert resp.status_code == 200
        else:
            assert resp.status_code == 401


async def test_token_permissions_control(client: TestClient, token: str, limited_user, limited_token: str):
    # Selective permissions control is done by client, not by server
    resp = await client.post(
        "/token",
        json={"permissions": ["store_management:2"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    j = resp.json()
    assert j["permissions"] == ["store_management:2"]
    # Limited token can't access higher scopes
    resp = await client.post(
        "/token",
        json={"permissions": ["store_management"]},
        headers={"Authorization": f"Bearer {limited_token}"},
    )
    assert resp.status_code == 403
    token_management_only_token = (
        await client.post("/token", json={"permissions": ["token_management"]}, headers={"Authorization": f"Bearer {token}"})
    ).json()["id"]
    assert (
        await client.post(
            "/token",
            json={"permissions": ["store_management"]},
            headers={"Authorization": f"Bearer {token_management_only_token}"},
        )
    ).status_code == 403
    # Strict mode: non-superuser user can't create superuser token
    resp = await client.post(
        "/token",
        json={"email": limited_user["email"], "password": static_data.USER_PWD, "permissions": ["server_management"]},
    )
    assert resp.status_code == 422
    # Non-strict mode: silently removes server_management permission
    resp = await client.post(
        "/token",
        json={
            "email": limited_user["email"],
            "password": static_data.USER_PWD,
            "permissions": ["server_management"],
            "strict": False,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["permissions"] == []


@Parametrization.autodetect_parameters()
@Parametrization.case(name="non-token-unauthorized", token_exists=False, authorized=False)
@Parametrization.case(name="non-token-authorized", token_exists=False, authorized=True)
@Parametrization.case(name="token-unauthorized", token_exists=True, authorized=False)
@Parametrization.case(name="token-authorized", token_exists=True, authorized=True)
async def test_delete_token(client: TestClient, token: str, token_exists: bool, authorized: bool):
    fetch_token = token if token_exists else 1
    resp = await client.delete(
        f"/token/{fetch_token}",
        headers={"Authorization": f"Bearer {token}"} if authorized else {},
    )
    if authorized:
        if token_exists:
            assert resp.status_code == 200
        else:
            assert resp.status_code == 404
    else:
        assert resp.status_code == 401


async def test_management_commands(client: TestClient, log_file: str, token: str, limited_token: str):
    assert (await client.post("/manage/update")).status_code == 401
    assert (await client.post("/manage/update", headers={"Authorization": f"Bearer {limited_token}"})).status_code == 403
    assert (await client.post("/manage/update", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (await client.post("/manage/restart", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (await client.post("/manage/cleanup/images", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (await client.post("/manage/cleanup/logs", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (await client.post("/manage/cleanup", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (await client.post("/manage/backups/backup", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (await client.get("/manage/backups/download/1", headers={"Authorization": f"Bearer {token}"})).status_code == 400
    assert (
        await client.post(
            "/manage/backups/restore",
            headers={"Authorization": f"Bearer {token}"},
            files={"backup": ("backup.tar.gz", b"test")},
        )
    ).status_code == 200  # requires uploading file
    assert (await client.get("/manage/daemons", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    with enabled_logs():
        assert (await client.post("/manage/cleanup", headers={"Authorization": f"Bearer {token}"})).status_code == 200
        assert not os.path.exists(log_file)


async def test_policies(client: TestClient, token: str):
    resp = await client.get("/manage/policies")
    assert resp.status_code == 200
    assert resp.json() == {
        "allow_anonymous_configurator": True,
        "disable_registration": False,
        "require_verified_email": False,
        "allow_file_uploads": True,
        "discourage_index": False,
        "check_updates": True,
        "staging_updates": False,
        "captcha_sitekey": "",
        "admin_theme_url": "",
        "captcha_type": schemes.CaptchaType.NONE,
        "use_html_templates": False,
        "global_templates": {
            "forgotpassword": "",
            "verifyemail": "",
        },
        "explorer_urls": {
            "btc": static_data.DEFAULT_EXPLORER,
        },
        "rpc_urls": {},
    }
    assert (await client.post("/manage/policies")).status_code == 401
    resp = await client.post(
        "/manage/policies",
        json={"disable_registration": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "allow_anonymous_configurator": True,
        "disable_registration": True,
        "require_verified_email": False,
        "allow_file_uploads": True,
        "discourage_index": False,
        "check_updates": True,
        "staging_updates": False,
        "captcha_sitekey": "",
        "captcha_secretkey": "",
        "admin_theme_url": "",
        "captcha_type": schemes.CaptchaType.NONE,
        "use_html_templates": False,
        "global_templates": {
            "forgotpassword": "",
            "verifyemail": "",
        },
        "explorer_urls": {
            "btc": static_data.DEFAULT_EXPLORER,
        },
        "rpc_urls": {},
        "email_settings": schemes.EmailSettings().model_dump(),
    }
    assert (await client.post("/users", json=static_data.POLICY_USER)).status_code == 422  # registration is off
    # Test for loading data from db instead of loading scheme's defaults
    assert (await client.get("/manage/policies")).json() == {
        "allow_anonymous_configurator": True,
        "disable_registration": True,
        "require_verified_email": False,
        "allow_file_uploads": True,
        "discourage_index": False,
        "check_updates": True,
        "staging_updates": False,
        "captcha_sitekey": "",
        "admin_theme_url": "",
        "captcha_type": schemes.CaptchaType.NONE,
        "use_html_templates": False,
        "global_templates": {
            "forgotpassword": "",
            "verifyemail": "",
        },
        "explorer_urls": {
            "btc": static_data.DEFAULT_EXPLORER,
        },
        "rpc_urls": {},
    }
    resp = await client.post(
        "/manage/policies",
        json={"disable_registration": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "allow_anonymous_configurator": True,
        "disable_registration": False,
        "require_verified_email": False,
        "allow_file_uploads": True,
        "discourage_index": False,
        "check_updates": True,
        "staging_updates": False,
        "captcha_sitekey": "",
        "captcha_secretkey": "",
        "admin_theme_url": "",
        "captcha_type": schemes.CaptchaType.NONE,
        "use_html_templates": False,
        "global_templates": {
            "forgotpassword": "",
            "verifyemail": "",
        },
        "explorer_urls": {
            "btc": static_data.DEFAULT_EXPLORER,
        },
        "rpc_urls": {},
        "email_settings": schemes.EmailSettings().model_dump(),
    }
    assert (await client.post("/users", json=static_data.POLICY_USER)).status_code == 200  # registration is on again
    resp = await client.get("/manage/stores")
    assert resp.status_code == 200
    assert resp.json() == {"pos_id": ""}
    assert (await client.post("/manage/stores")).status_code == 401
    resp = await client.post(
        "/manage/stores",
        json={"pos_id": "2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"pos_id": "2"}
    assert (await client.get("/manage/stores")).json() == {"pos_id": "2"}
    resp = await client.post(
        "/manage/stores",
        json={"pos_id": "1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"pos_id": "1"}


async def test_policies_store_created(client: TestClient, store):
    resp = await client.get("/manage/stores")
    assert resp.status_code == 200
    assert resp.json()["pos_id"] == store["id"]


async def test_no_token_management(client: TestClient, limited_token: str):
    assert (await client.get("/token/current", headers={"Authorization": f"Bearer {limited_token}"})).status_code == 200
    assert (await client.get("/token", headers={"Authorization": f"Bearer {limited_token}"})).status_code == 403
    assert (await client.get("/token/count", headers={"Authorization": f"Bearer {limited_token}"})).status_code == 403
    assert (
        await client.patch(
            f"/token/{limited_token}",
            headers={"Authorization": f"Bearer {limited_token}"},
        )
    ).status_code == 403
    assert (
        await client.delete(
            f"/token/{limited_token}",
            headers={"Authorization": f"Bearer {limited_token}"},
        )
    ).status_code == 403


async def test_non_superuser_permissions(client: TestClient, user, limited_user):
    resp = await client.post(
        "/token",
        json={
            "email": limited_user["email"],
            "password": static_data.USER_PWD,
            "permissions": ["full_control"],
            "strict": False,
        },
    )
    token = resp.json()["access_token"]
    assert (await client.get("/token", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (await client.get(f"/users/{user['id']}", headers={"Authorization": f"Bearer {token}"})).status_code == 403


async def test_notification_list(client: TestClient):
    resp = await client.get("/notifications/list")
    assert resp.status_code == 200
    assert resp.json() == {
        "count": len(settings.settings.notifiers),
        "next": None,
        "previous": None,
        "result": list(settings.settings.notifiers.keys()),
    }


async def test_notification_schema(client: TestClient):
    resp = await client.get("/notifications/schema")
    assert resp.status_code == 200
    assert resp.json() == settings.settings.notifiers


async def test_template_list(client: TestClient):
    resp = await client.get("/templates/list")
    assert resp.status_code == 200
    assert resp.json() == {
        "count": len(settings.settings.template_manager.templates_strings),
        "next": None,
        "previous": None,
        "result": settings.settings.template_manager.templates_strings,
    }
    resp1 = await client.get("/templates/list?show_all=true")
    result = [v for template_set in settings.settings.template_manager.templates_strings.values() for v in template_set]
    assert resp1.status_code == 200
    assert resp1.json() == {
        "count": len(result),
        "next": None,
        "previous": None,
        "result": result,
    }
    resp2 = await client.get("/templates/list?applicable_to=product")
    assert resp2.status_code == 200
    assert resp2.json() == {
        "count": len(settings.settings.template_manager.templates_strings["product"]),
        "next": None,
        "previous": None,
        "result": settings.settings.template_manager.templates_strings["product"],
    }
    resp3 = await client.get("/templates/list?applicable_to=notfound")
    assert resp3.status_code == 200
    assert resp3.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "result": [],
    }


async def test_services(client: TestClient, token: str):
    resp = await client.get("/tor/services")
    assert resp.status_code == 200
    assert resp.json() == await tor_ext.get_data("anonymous_services_dict", {}, json_decode=True)
    resp2 = await client.get("/tor/services", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json() == await tor_ext.get_data("services_dict", {}, json_decode=True)


async def test_export_invoices(client: TestClient, token: str, limited_user):
    limited_token = (await create_token(client, limited_user))["access_token"]
    invoice = await create_invoice(client, limited_user["id"], limited_token)
    await client.post(
        "/invoices/batch",
        json={"ids": [invoice["id"]], "command": "mark_complete"},
        headers={"Authorization": f"Bearer {limited_token}"},
    )
    assert (await client.get("/invoices/export")).status_code == 401
    assert (
        await client.get("/invoices/export?all_users=true", headers={"Authorization": f"Bearer {limited_token}"})
    ).status_code == 403
    assert len((await client.get("/invoices/export", headers={"Authorization": f"Bearer {limited_token}"})).json()) > 0
    json_resp = await client.get("/invoices/export", headers={"Authorization": f"Bearer {token}"})
    assert json_resp.status_code == 200
    assert isinstance(json_resp.json(), list)
    assert len(json_resp.json()) == 0
    assert "bitcart-export" in json_resp.headers["content-disposition"]
    resp2 = await client.get("/invoices/export?export_format=json", headers={"Authorization": f"Bearer {token}"})
    assert resp2.json() == json_resp.json()
    csv_resp = await client.get("/invoices/export?export_format=csv", headers={"Authorization": f"Bearer {token}"})
    assert csv_resp.status_code == 200
    assert "bitcart-export" in csv_resp.headers["content-disposition"]
    assert csv_resp.text.endswith("\r\n")
    json_resp = await client.get("/invoices/export?all_users=true", headers={"Authorization": f"Bearer {token}"})
    data = json_resp.json()
    assert len(data) == 1
    assert data[0]["id"] == invoice["id"]
    assert "payments" not in data[0]
    assert (
        "payments"
        in (
            await client.get("/invoices/export?all_users=true&add_payments=true", headers={"Authorization": f"Bearer {token}"})
        ).json()[0]
    )


async def test_batch_commands(client: TestClient, token: str, store):
    store_id = store["id"]
    assert (await client.post("/invoices/batch")).status_code == 401
    assert (await client.post("/invoices/batch", headers={"Authorization": f"Bearer {token}"})).status_code == 422
    assert (
        await client.post("/invoices/batch", json={"ids": [], "command": "test"}, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404
    assert (
        await client.post("/invoices", json={"store_id": "-1", "price": 0.5}, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404
    resp1 = await client.post(
        "/invoices", json={"store_id": store_id, "price": 0.5}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp1.status_code == 200
    invoice_id_1 = resp1.json()["id"]
    resp2 = await client.post(
        "/invoices", json={"store_id": store_id, "price": 0.5}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp2.status_code == 200
    invoice_id_2 = resp2.json()["id"]
    assert (
        await client.post(
            "/invoices/batch",
            json={"ids": [invoice_id_1, invoice_id_2], "command": "delete"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert (await client.get("/invoices", headers={"Authorization": f"Bearer {token}"})).json()["result"] == []
    resp3 = await client.post(
        "/invoices", json={"store_id": store_id, "price": 0.5}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp3.status_code == 200
    invoice_id_3 = resp3.json()["id"]
    assert (
        await client.post(
            "/invoices/batch",
            json={"ids": [invoice_id_3], "command": "mark_invalid"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert (await client.get(f"/invoices/{invoice_id_3}", headers={"Authorization": f"Bearer {token}"})).json()[
        "status"
    ] == "invalid"
    assert (
        await client.post(
            "/invoices/batch",
            json={"ids": [invoice_id_3], "command": "mark_complete"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert (await client.get(f"/invoices/{invoice_id_3}", headers={"Authorization": f"Bearer {token}"})).json()[
        "status"
    ] == "complete"


async def test_wallet_ws(client, token: str):
    r = await client.post(
        "/wallets",
        json={"name": "testws1", "xpub": static_data.TEST_XPUB},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    wallet_id = r.json()["id"]
    async with aconnect_ws(f"/ws/wallets/{wallet_id}?token={token}", client) as websocket:
        await asyncio.sleep(1)
        await utils.redis.publish_message(
            f"wallet:{wallet_id}",
            {"status": "success", "balance": str((await BTC(xpub=static_data.TEST_XPUB).balance())["confirmed"])},
        )
        await check_ws_response2(websocket)
    with pytest.raises(WebSocketDisconnect) as exc:
        async with aconnect_ws(f"/ws/wallets/{wallet_id}", client) as websocket:
            await check_ws_response2(websocket)
    assert exc.value.code == WS_1008_POLICY_VIOLATION
    with pytest.raises(WebSocketDisconnect) as exc:
        async with aconnect_ws(f"/ws/wallets/{wallet_id}?token=x", client) as websocket:
            await check_ws_response2(websocket)
    assert exc.value.code == WS_1008_POLICY_VIOLATION
    with pytest.raises(WebSocketDisconnect) as exc:
        async with aconnect_ws(f"/ws/wallets/555?token={token}", client) as websocket:
            await check_ws_response2(websocket)
    assert exc.value.code == WS_1008_POLICY_VIOLATION


async def test_invoice_ws(client, token: str, store):
    store_id = store["id"]
    r = await client.post("/invoices", json={"store_id": store_id, "price": 5}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    invoice_id = data["id"]
    async with aconnect_ws(f"/ws/invoices/{invoice_id}", client) as websocket:
        await asyncio.sleep(1)
        await invoices.new_payment_handler(
            DummyInstance(),
            None,
            data["payments"][0]["lookup_field"],
            InvoiceStatus.UNCONFIRMED,
            None,
            [],
            data["payments"][0]["amount"],
        )  # emulate paid invoice
        await check_ws_response(websocket, data["payments"][0]["amount"])
    async with aconnect_ws(
        f"/ws/invoices/{invoice_id}", client
    ) as websocket2:  # test if after invoice was completed websocket returns immediately
        await check_ws_response_complete(websocket2, data["payments"][0]["amount"])
    with pytest.raises(WebSocketDisconnect) as exc:
        async with aconnect_ws("/ws/invoices/555", client) as websocket:
            await check_ws_response(websocket, 0)
    assert exc.value.code == WS_1008_POLICY_VIOLATION
    with pytest.raises(WebSocketDisconnect) as exc:
        async with aconnect_ws("/ws/invoices/invalid_id", client) as websocket:
            await check_ws_response(websocket, 0)
    assert exc.value.code == WS_1008_POLICY_VIOLATION


@pytest.mark.parametrize("currencies", ["", "DUMMY", "btc"])
async def test_create_invoice_discount(client: TestClient, token: str, store, currencies: str):  # TODO: improve this test
    store_id = store["id"]
    # create discount
    new_discount = {
        "name": "apple",
        "percent": 50,
        "currencies": currencies,
        "promocode": "testpromo",
        "end_date": "2099-12-31 00:00:00.000000",
    }
    create_discount_resp = await client.post("/discounts", json=new_discount, headers={"Authorization": f"Bearer {token}"})
    assert create_discount_resp.status_code == 200
    discount_id = create_discount_resp.json()["id"]
    # create product
    new_product = {"name": "apple", "price": 0.80, "quantity": 1.0, "store_id": store_id, "discounts": [discount_id]}
    create_product_resp = await client.post(
        "/products", data={"data": json_module.dumps(new_product)}, headers={"Authorization": f"Bearer {token}"}
    )
    assert create_product_resp.status_code == 200
    product_id = create_product_resp.json()["id"]
    invoice_resp = await client.post(
        "/invoices",
        json={"store_id": store_id, "price": 0.5, "products": [product_id], "promocode": "testpromo"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert invoice_resp.status_code == 200
    assert {
        "price": "0.50",
        "store_id": store_id,
        "promocode": "testpromo",
        "products": [product_id],
    }.items() < invoice_resp.json().items()
    assert (
        await client.delete(f"/invoices/{invoice_resp.json()['id']}", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200


async def test_get_or_create_invoice_by_order_id(client: TestClient, token: str, store):
    store_id = store["id"]
    resp = await client.post("/invoices/order_id/1", json={"price": 5, "store_id": store_id})
    assert resp.status_code == 200
    assert resp.json()["order_id"] == "1"
    assert (await client.post("/invoices/order_id/1", json={"price": 5, "store_id": store_id})).json()["id"] == resp.json()[
        "id"
    ]
    await invoices.new_payment_handler(DummyInstance(), None, resp.json()["payments"][0]["lookup_field"], "complete", None)
    assert (await client.post("/invoices/order_id/1", json={"price": 5, "store_id": store_id})).json()["id"] == resp.json()[
        "id"
    ]


async def test_get_max_product_price(client: TestClient, token: str, store):
    # create product
    price = 999999.0
    new_product = {"name": "apple", "price": price, "quantity": 1.0, "store_id": store["id"]}
    create_product_resp = await client.post(
        "/products", data={"data": json_module.dumps(new_product)}, headers={"Authorization": f"Bearer {token}"}
    )
    assert create_product_resp.status_code == 200
    maxprice_resp = await client.get(
        f"/products/maxprice?store={new_product['store_id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert maxprice_resp.status_code == 200
    assert maxprice_resp.json() == price


async def test_create_product_with_image(client: TestClient, token: str, image: bytes, store):
    store_id = store["id"]
    new_product = {"name": "sunflower", "price": 0.1, "quantity": 1.0, "store_id": store_id}
    # post
    create_product_resp = await client.post(
        "/products",
        data={"data": json_module.dumps(new_product)},
        files={"image": image},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_product_resp.status_code == 200
    product_dict = create_product_resp.json()
    assert isinstance(product_dict["image"], str)
    assert product_dict["image"] == f"images/products/{product_dict['id']}.png"
    # patch
    patch_product_resp = await client.patch(
        f"/products/{product_dict['id']}",
        data={
            "data": json_module.dumps(
                {"price": 0.15, "quantity": 2.0, "user_id": product_dict["user_id"], "name": "sunflower"}
            )
        },
        files={"image": image},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_product_resp.status_code == 200
    assert os.path.exists(os.path.join(settings.settings.products_image_dir, f"{product_dict['id']}.png"))
    assert (
        await client.post(
            "/products/batch",
            json={"ids": [product_dict["id"]], "command": "delete"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert not os.path.exists(os.path.join(settings.settings.products_image_dir, f"{product_dict['id']}.png"))


async def test_create_invoice_without_coin_rate(client, token: str, mocker, store):
    store_id = store["id"]
    price = 9.9
    # mock coin rate missing
    mocker.patch(
        "api.settings.settings.exchange_rates.get_rate",
        side_effect=lambda exchange, pair=None: {} if pair is None else Decimal("NaN"),
    )
    # create invoice
    r = await client.post(
        "/invoices",
        json={"store_id": store_id, "price": price, "currency": "DUMMY"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    result = r.json()
    assert float(result["price"]) == price
    assert result["price"] == "9.90"


async def test_create_invoice_and_pay(client, token: str, store):
    store_id = store["id"]
    # create invoice
    r = await client.post("/invoices", json={"store_id": store_id, "price": 9.9}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    invoice_id = data["id"]
    # get payment
    payment_method = await utils.database.get_object(
        models.PaymentMethod,
        invoice_id,
        custom_query=models.PaymentMethod.query.where(models.PaymentMethod.invoice_id == invoice_id),
    )
    await invoices.new_payment_handler(
        DummyInstance(), None, data["payments"][0]["lookup_field"], "complete", None
    )  # pay the invoice
    # validate invoice paid_currency
    final_invoice = await utils.database.get_object(models.Invoice, invoice_id)
    assert final_invoice.paid_currency == payment_method.currency.upper()
    assert final_invoice.payment_id == payment_method.id
    await client.delete(f"/invoices/{invoice_id}", headers={"Authorization": f"Bearer {token}"})


async def test_get_public_store(client: TestClient, store):
    store_id = store["id"]
    user_id = (await client.post("/users", json={"email": "test2auth@example.com", "password": "test12345"})).json()["id"]
    new_token = (
        await client.post(
            "/token",
            json={"email": "test2auth@example.com", "password": "test12345", "permissions": ["full_control"]},
        )
    ).json()["access_token"]
    # When logged in, allow limited access to public objects
    PUBLIC_KEYS = {
        "created",
        "name",
        "default_currency",
        "id",
        "user_id",
        "checkout_settings",
        "theme_settings",
        "currency_data",
        "metadata",
    }
    assert (
        set((await client.get(f"/stores/{store_id}", headers={"Authorization": f"Bearer {new_token}"})).json().keys())
        == PUBLIC_KEYS
    )
    await client.delete(f"/users/{user_id}")
    # get store without user
    store = await client.get(f"/stores/{store_id}")
    assert set(store.json().keys()) == PUBLIC_KEYS


async def test_get_product_params(client: TestClient, token: str, product):
    product_id = product["id"]
    store_id = product["store_id"]
    assert (await client.get(f"/products/{product_id}", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert (
        await client.get(f"/products/{product_id}?store={store_id}", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200
    assert (
        await client.get(f"/products/{product_id}?store=555", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404


async def test_product_count_params(client: TestClient, token: str):
    resp = await client.get(
        "/products/count?sale=true&store=2&category=Test&min_price=0.0001&max_price=100.0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.json() == 0


async def test_updatecheck(client: TestClient):
    resp = await client.get("/update/check")
    assert resp.status_code == 200
    assert resp.json() == {"update_available": False, "tag": None}


async def test_logs_list(client: TestClient, token: str):
    assert (await client.get("/manage/logs")).status_code == 401
    resp = await client.get("/manage/logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []
    with enabled_logs():
        assert (await client.get("/manage/logs", headers={"Authorization": f"Bearer {token}"})).json() == [
            "bitcart.log",
            "bitcart20210821.log",
        ]


async def test_logs_get(client: TestClient, token: str):
    assert (await client.get("/manage/logs/1")).status_code == 401
    assert (await client.get("/manage/logs/1", headers={"Authorization": f"Bearer {token}"})).status_code == 400
    with enabled_logs():
        assert (await client.get("/manage/logs/1", headers={"Authorization": f"Bearer {token}"})).status_code == 404
        resp = await client.get("/manage/logs/bitcart.log", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == "Test"


async def test_logs_delete(client: TestClient, log_file: str, token: str):
    log_name = os.path.basename(log_file)
    assert (await client.delete("/manage/logs/1")).status_code == 401
    assert (await client.delete("/manage/logs/1", headers={"Authorization": f"Bearer {token}"})).status_code == 400
    # Tests that it is impossible to delete files outside logs directory:
    assert (await client.delete("/manage/logs//root/path", headers={"Authorization": f"Bearer {token}"})).status_code == 404
    assert (
        await client.delete("/manage/logs/..%2F.gitignore", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404
    with enabled_logs():
        assert (await client.delete("/manage/logs/1", headers={"Authorization": f"Bearer {token}"})).status_code == 404
        assert (
            await client.delete("/manage/logs/bitcart.log", headers={"Authorization": f"Bearer {token}"})
        ).status_code == 403
        resp = await client.delete(f"/manage/logs/{log_name}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() is True
    assert not os.path.exists(log_file)


async def test_cryptos(client: TestClient):
    resp = await client.get("/cryptos")
    assert resp.status_code == 200
    assert resp.json() == {
        "count": len(settings.settings.cryptos),
        "next": None,
        "previous": None,
        "result": list(settings.settings.cryptos.keys()),
    }


async def test_wallet_balance(client: TestClient, token: str, wallet: dict):
    assert (await client.get(f"/wallets/{wallet['id']}/balance")).status_code == 401
    resp = await client.get(f"/wallets/{wallet['id']}/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {
        "confirmed": "0.01000000",
        "lightning": "0.00000000",
        "unconfirmed": "0.00000000",
        "unmatured": "0.00000000",
    }


async def test_lightning_endpoints(client: TestClient, token: str, wallet):
    wallet_id = wallet["id"]
    assert (await client.get(f"/wallets/{wallet_id}/checkln")).status_code == 401
    assert (await client.get("/wallets/555/checkln", headers={"Authorization": f"Bearer {token}"})).status_code == 404
    assert (await client.get("/wallets/555/channels", headers={"Authorization": f"Bearer {token}"})).status_code == 404
    assert (
        await client.post(
            "/wallets/555/channels/open", json={"node_id": "test", "amount": 0.1}, headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 404
    assert (
        await client.post(
            "/wallets/555/channels/close", json={"channel_point": "test"}, headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 404
    assert (
        await client.post("/wallets/555/lnpay", json={"invoice": "test"}, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 404
    resp = await client.get(f"/wallets/{wallet_id}/checkln", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() is False
    resp2 = await client.get(f"/wallets/{wallet_id}/channels", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json() == []
    assert (
        await client.post(
            f"/wallets/{wallet_id}/channels/open",
            json={"node_id": "test", "amount": 0.1},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/wallets/{wallet_id}/channels/close",
            json={"channel_point": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/wallets/{wallet_id}/lnpay", json={"invoice": "test"}, headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 400


async def test_multiple_wallets_same_currency(client, token: str, user):
    wallet1_id = (await create_wallet(client, user["id"], token))["id"]
    wallet2_id = (await create_wallet(client, user["id"], token))["id"]
    resp = await client.post(
        "/stores",
        json={"name": "Multiple Currency", "wallets": [wallet1_id, wallet2_id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    store_id = resp.json()["id"]
    resp = await client.post("/invoices", json={"price": 5, "store_id": store_id})
    assert resp.status_code == 200
    resp = resp.json()
    assert len(resp["payments"]) == 2
    assert resp["payments"][0]["name"] == "BTC (1)"
    assert resp["payments"][1]["name"] == "BTC (2)"


async def test_change_store_checkout_settings(client: TestClient, token: str, store):
    store_id = store["id"]
    assert (await client.patch(f"/stores/{store_id}/checkout_settings")).status_code == 401
    assert (
        await client.patch(
            "/stores/555/checkout_settings", json={"expiration": 60}, headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 404
    resp = await client.patch(
        f"/stores/{store_id}/checkout_settings", json={"expiration": 60}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    # Changes only the settings provided
    default_values = schemes.StoreCheckoutSettings().model_dump()
    assert resp.json()["checkout_settings"] == {**default_values, "expiration": 60}
    assert len(resp.json()["wallets"]) > 0
    resp2 = await client.get(f"/stores/{store_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json() == resp.json()
    resp = await client.patch(
        f"/stores/{store_id}/checkout_settings",
        json={"use_html_templates": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["checkout_settings"] == {**default_values, "expiration": 60, "use_html_templates": True}


async def test_change_store_theme_settings(client: TestClient, token: str, store):
    store_id = store["id"]
    assert (await client.patch(f"/stores/{store_id}/theme_settings")).status_code == 401
    assert (
        await client.patch(
            "/stores/555/theme_settings", json={"store_theme_url": "url"}, headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 404
    resp = await client.patch(
        f"/stores/{store_id}/theme_settings", json={"store_theme_url": "url"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    # Changes only the settings provided
    default_values = schemes.StoreThemeSettings().model_dump()
    assert resp.json()["theme_settings"] == {**default_values, "store_theme_url": "url"}
    assert len(resp.json()["wallets"]) > 0
    resp2 = await client.get(f"/stores/{store_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json() == resp.json()
    resp = await client.patch(
        f"/stores/{store_id}/theme_settings",
        json={"checkout_theme_url": "url2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["theme_settings"] == {**default_values, "store_theme_url": "url", "checkout_theme_url": "url2"}


async def test_products_list(client: TestClient):
    assert (await client.get("/products")).status_code == 401
    assert (await client.get("/products?store=1")).status_code == 200
    resp = await client.get("/products?store=0")
    assert resp.status_code == 200
    assert resp.json()["result"] == []


async def test_configurator(client: TestClient, token: str):
    assert (await client.post("/configurator/deploy")).status_code == 422
    assert (
        await client.post(
            "/manage/policies",
            json={"allow_anonymous_configurator": False},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert (await client.post("/configurator/deploy", json=static_data.SCRIPT_SETTINGS)).status_code == 422
    assert (
        await client.post(
            "/manage/policies",
            json={"allow_anonymous_configurator": True},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    resp = await client.post("/configurator/deploy", json=static_data.SCRIPT_SETTINGS)
    assert resp.status_code == 200
    assert resp.json()["success"]
    script = resp.json()["output"]
    assert "sudo su -" in script
    assert f"git clone {DOCKER_REPO_URL} bitcart-docker" in script
    assert "BITCART_CRYPTOS=btc" in script
    assert "BITCART_HOST=bitcart.ai" in script
    assert "BTC_NETWORK=testnet" in script
    assert "BTC_LIGHTNING=True" in script
    assert "BITCART_ADDITIONAL_COMPONENTS=custom,tor" in script
    deploy_settings = static_data.SCRIPT_SETTINGS.copy()
    deploy_settings["mode"] = "Remote"
    resp = await client.post("/configurator/deploy", json=deploy_settings)
    assert (await client.get("/configurator/deploy-result/1")).status_code == 404
    assert resp.status_code == 200
    assert not resp.json()["success"]
    deploy_id = resp.json()["id"]
    resp2 = await client.get(f"/configurator/deploy-result/{deploy_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert not data["success"]
    assert data["id"] == deploy_id
    deploy_settings = static_data.SCRIPT_SETTINGS.copy()
    deploy_settings["mode"] = "Current"
    assert (await client.post("/configurator/deploy", json=deploy_settings)).status_code == 401
    resp = await client.post("/configurator/deploy", json=deploy_settings, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert not resp.json()["success"]
    deploy_id = resp.json()["id"]
    resp2 = await client.get(f"/configurator/deploy-result/{deploy_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert not data["success"]
    assert data["id"] == deploy_id


async def test_supported_cryptos(client: TestClient):
    resp = await client.get("/cryptos/supported")
    assert resp.status_code == 200
    assert resp.json() == SUPPORTED_CRYPTOS


async def test_get_server_settings(client: TestClient, token: str):
    assert (await client.get("/configurator/server-settings")).status_code == 405
    assert (await client.post("/configurator/server-settings")).status_code == 401
    resp = await client.post("/configurator/server-settings", json={"host": ""})
    assert resp.status_code == 200
    assert resp.json() == static_data.FALLBACK_SERVER_SETTINGS
    resp = await client.post("/configurator/server-settings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == static_data.FALLBACK_SERVER_SETTINGS  # SSH unconfigured


async def test_unauthorized_m2m_access(client: TestClient, token: str, limited_user, wallet):
    wallet_id = wallet["id"]
    # No unauthorized anonymous access
    assert (await client.post("/stores", json={"name": "new store", "wallets": [wallet_id]})).status_code == 401
    # The actual owner can operate related objects
    resp = await client.post(
        "/stores", json={"name": "new store", "wallets": [wallet_id]}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    store_id = resp.json()["id"]
    await client.delete(f"/stores/{store_id}", headers={"Authorization": f"Bearer {token}"})
    token_usual = (
        await client.post(
            "/token",
            json={"email": limited_user["email"], "password": static_data.USER_PWD, "permissions": ["full_control"]},
        )
    ).json()["access_token"]
    assert (
        await client.post(
            "/stores", json={"name": "new store", "wallets": ["2"]}, headers={"Authorization": f"Bearer {token_usual}"}
        )
    ).status_code == 403  # Can't access other users' related objects


async def get_wallet_balances(client, token):
    return (await client.get("/wallets/balance", headers={"Authorization": f"Bearer {token}"})).json()


async def test_users_display_balance(client: TestClient, token: str, wallet):
    assert Decimal(await get_wallet_balances(client, token)) > 1
    assert (await client.post("/users/me/settings")).status_code == 401
    resp = await client.post(
        "/users/me/settings", json={"balance_currency": "BTC"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    # Changes only the settings provided
    default_values = schemes.UserPreferences().model_dump()
    assert resp.json()["settings"] == {**default_values, "balance_currency": "BTC"}
    assert float(await get_wallet_balances(client, token)) == 0.01
    resp = await client.post(
        "/users/me/settings",
        json={"balance_currency": "USD"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["settings"] == default_values
    assert Decimal(await get_wallet_balances(client, token)) > 1


async def test_invoice_products_access_control(client: TestClient):
    user1 = await create_user(client)
    user2 = await create_user(client)
    token1 = (await create_token(client, user1))["access_token"]
    token2 = (await create_token(client, user2))["access_token"]
    product1 = await create_product(client, user1["id"], token1)
    product2 = await create_product(client, user2["id"], token2)
    store_id1 = product1["store_id"]
    store_id2 = product2["store_id"]
    product_id1 = product1["id"]
    product_id2 = product2["id"]
    assert (
        await client.post("/invoices", json={"price": 5, "store_id": store_id1, "products": [product_id1]})
    ).status_code == 200
    assert (
        await client.post("/invoices", json={"price": 5, "store_id": store_id1, "products": [product_id2]})
    ).status_code == 403
    assert (
        await client.post("/invoices", json={"price": 5, "store_id": store_id2, "products": [product_id2]})
    ).status_code == 200
    assert (
        await client.post("/invoices", json={"price": 5, "store_id": store_id2, "products": [product_id1]})
    ).status_code == 403


async def test_wallets_labels(client, token: str, user):
    wallet1_id = (await create_wallet(client, user["id"], token))["id"]
    wallet2_id = (await create_wallet(client, user["id"], token, label="customlabel"))["id"]
    resp = await client.post(
        "/stores",
        json={"name": "Multiple Currency", "wallets": [wallet1_id, wallet2_id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    store_id = resp.json()["id"]
    resp = await client.post("/invoices", json={"price": 5, "store_id": store_id})
    assert resp.status_code == 200
    resp = resp.json()
    assert len(resp["payments"]) == 2
    assert resp["payments"][0]["name"] == "BTC"
    assert resp["payments"][1]["name"] == "customlabel"


async def test_backup_providers(client: TestClient):
    resp = await client.get("/manage/backups/providers")
    assert resp.status_code == 200
    assert resp.json() == BACKUP_PROVIDERS


async def test_backup_frequencies(client: TestClient):
    resp = await client.get("/manage/backups/frequencies")
    assert resp.status_code == 200
    assert resp.json() == BACKUP_FREQUENCIES


async def test_backup_policies(client: TestClient, token):
    assert (await client.get("/manage/backups")).status_code == 401
    resp = await client.get("/manage/backups", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {
        "provider": "local",
        "scheduled": False,
        "frequency": "weekly",
        "environment_variables": {},
    }
    assert (await client.post("/manage/backups")).status_code == 401
    resp = await client.post(
        "/manage/backups",
        json={"scheduled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "provider": "local",
        "scheduled": True,
        "frequency": "weekly",
        "environment_variables": {},
    }


async def test_products_pagination_deleted_store(client: TestClient, token, store, user):
    product = await create_product(client, user["id"], token, store_id=store["id"])
    assert (await client.get("/products")).status_code == 401
    resp = await client.get("/products", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["result"][0] == product
    new_resp = {**product, "store_id": None}
    await client.delete(f"/stores/{store['id']}", headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/products", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["result"][0] == new_resp


@pytest.mark.parametrize(
    ("name", "expected", "updated"),
    [
        ("buyer_email", "test@example.com", "test2@example.com"),
        ("shipping_address", "test", "test2"),
        ("notes", "test", "test2"),
    ],
)
async def test_invoice_update_customer(client: TestClient, user, token, name, expected, updated):
    invoice = await create_invoice(client, user["id"], token)
    invoice_id = invoice["id"]
    assert (await client.patch(f"/invoices/{invoice_id}")).status_code == 401
    assert (await client.patch(f"/invoices/{invoice_id}/customer")).status_code == 422
    assert (await client.patch("/invoices/test/customer", json={name: expected})).status_code == 404
    # Can edit only allowed fields
    assert (await client.patch(f"/invoices/{invoice_id}/customer", json={"price": 1})).json()["price"] == invoice["price"]
    # Empty string is treated normally
    assert (await client.patch(f"/invoices/{invoice_id}/customer", json={"buyer_email": ""})).json()["buyer_email"] == ""
    resp = await client.patch(f"/invoices/{invoice_id}/customer", json={name: expected})
    assert resp.status_code == 200
    assert resp.json()[name] == expected
    # when set, don't change anymore
    assert (await client.patch(f"/invoices/{invoice_id}/customer", json={name: updated})).json()[name] == expected


async def test_get_tokens_btc(client: TestClient):
    resp = await client.get("/cryptos/tokens/btc")
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "result": [], "previous": None, "next": None}
    resp = await client.get("/cryptos/tokens/btc/abi")
    assert resp.status_code == 200
    assert resp.json() == []


class NotRunningBTC:
    coin_name = "BTC"

    class server:
        @staticmethod
        def getinfo():
            raise BitcartBaseError("Not running")


async def test_syncinfo(client: TestClient, token, mocker):
    def find_element(elements, name):
        for element in elements:
            if element["currency"] == name:
                return element

    assert (await client.get("/manage/syncinfo")).status_code == 401
    resp = await client.get("/manage/syncinfo", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    item = find_element(data, "BTC")
    assert item["running"] is True
    assert item["synchronized"] is True
    assert item["blockchain_height"] > 0
    mocker.patch("api.settings.settings.cryptos", {"btc": NotRunningBTC()})
    data = (await client.get("/manage/syncinfo", headers={"Authorization": f"Bearer {token}"})).json()
    item = find_element(data, "BTC")
    assert item["running"] is False


async def test_create_invoice_randomize_wallets(client: TestClient, token, user):
    wallets = [await create_wallet(client, user["id"], token, xpub=xpub) for xpub in static_data.RANDOMIZE_TEST_XPUBS]
    store = await create_store(client, user["id"], token, custom_store_attrs={"wallets": [x["id"] for x in wallets]})
    invoice = await create_invoice(client, user["id"], token, store_id=store["id"])
    payments = invoice["payments"]
    idx = 1
    for payment in payments:
        assert payment["name"] == f"BTC ({idx})"
        idx += 1
    await client.patch(
        f"/stores/{store['id']}/checkout_settings",
        json={"randomize_wallet_selection": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    invoice = await create_invoice(client, user["id"], token, store_id=store["id"])
    assert len(invoice["payments"]) == 1
    assert invoice["payments"][0]["name"] == "BTC"
    is_mine_ok = defaultdict(bool)
    while True:
        invoice = await create_invoice(client, user["id"], token, store_id=store["id"])
        address = invoice["payments"][0]["payment_address"]
        for wallet, xpub in enumerate(static_data.RANDOMIZE_TEST_XPUBS):
            is_mine_ok[wallet] |= await BTC(xpub=xpub).server.ismine(address)
        if all(is_mine_ok.values()):
            break


async def test_get_default_explorer(client: TestClient):
    assert (await client.get("/cryptos/explorer/test")).status_code == 422
    resp = await client.get("/cryptos/explorer/btc")
    assert resp.status_code == 200
    assert resp.json() == static_data.DEFAULT_EXPLORER
    assert (await client.get("/cryptos/explorer/BTC")).json() == resp.json()


async def test_get_default_rpc(client: TestClient):
    assert (await client.get("/cryptos/rpc/test")).status_code == 422
    resp = await client.get("/cryptos/rpc/btc")
    assert resp.status_code == 200
    assert resp.json() == ""
    assert (await client.get("/cryptos/rpc/BTC")).json() == resp.json()


async def test_invoices_authorized_access(client: TestClient, store, token):
    assert (await client.post("/invoices", json={"price": 1, "store_id": store["id"]})).status_code == 200
    assert (
        await client.patch(
            f"/stores/{store['id']}/checkout_settings",
            json={"allow_anonymous_invoice_creation": False},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert (await client.post("/invoices", json={"price": 1, "store_id": store["id"]})).status_code == 403


async def test_wallet_schema(client: TestClient):
    resp = await client.get("/wallets/schema")
    assert resp.status_code == 200
    assert resp.json() == {"btc": {"required": [], "properties": [], "xpub_name": "Xpub"}}


async def test_invoices_payment_details(client: TestClient, user, token):
    invoice = await create_invoice(client, user["id"], token)
    invoice_id = invoice["id"]
    payment_id = invoice["payments"][0]["id"]
    assert (await client.patch(f"/invoices/{invoice_id}/details")).status_code == 422
    assert (
        await client.patch(f"/invoices/{invoice_id}/details", json={"id": payment_id, "address": "test"})
    ).status_code == 422
    assert (
        await client.patch(
            f"/invoices/{invoice['id']}/details",
            json={"id": "test", "address": static_data.PAYOUT_DESTINATION},
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/invoices/{invoice_id}/details", json={"id": payment_id, "address": static_data.PAYOUT_DESTINATION}
        )
    ).status_code == 422  # unsupported in BTC
    invoice = await create_invoice(client, user["id"], token)
    assert (
        await client.post(
            "/invoices/batch",
            json={"ids": [invoice["id"]], "command": "mark_complete"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/invoices/{invoice['id']}/details",
            json={"id": invoice["payments"][0]["id"], "address": static_data.PAYOUT_DESTINATION},
        )
    ).status_code == 422


async def test_ping_server_mail(client: TestClient, token: str):
    assert (await client.get("/manage/testping")).status_code == 401
    resp = await client.get("/manage/testping", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert not resp.json()


async def test_password_reset(client: TestClient, user, token, mocker):
    auth_code = None

    def func(url, code):
        nonlocal auth_code
        auth_code = code

    mocker.patch("api.utils.email.Email.is_enabled", return_value=True)
    mocker.patch("api.utils.email.Email.send_mail", return_value=True)
    mocker.patch("api.utils.routing.get_redirect_url", side_effect=func)
    assert (
        await client.post("/users/reset_password", json={"email": "notexisting@gmail.com", "next_url": "https://example.com"})
    ).status_code == 200
    assert (
        await client.post("/users/reset_password", json={"email": user["email"], "next_url": "https://example.com"})
    ).status_code == 200
    assert auth_code is not None
    assert (await client.post("/users/reset_password/finalize/notexisting", json={"password": "12345678"})).status_code == 422
    assert (await client.post(f"/users/reset_password/finalize/{auth_code}", json={"password": "12345678"})).status_code == 200
    assert (await client.post(f"/users/reset_password/finalize/{auth_code}", json={"password": "12345678"})).status_code == 422
    assert (await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401
    assert (await client.post("/token", json={"email": user["email"], "password": static_data.USER_PWD})).status_code == 401
    assert (await client.post("/token", json={"email": user["email"], "password": "12345678"})).status_code == 200


async def test_products_quantity_management(client: TestClient, user, token, store):
    store_id = store["id"]
    product1 = await create_product(client, user["id"], token, store_id=store_id, quantity=-1)
    product2 = await create_product(client, user["id"], token, store_id=store_id, quantity=5)
    invoice1 = await create_invoice(client, user["id"], token, store_id=store_id, products=[product1["id"]])
    invoice2 = await create_invoice(client, user["id"], token, store_id=store_id, products=[product2["id"]])
    await client.post(
        "/invoices/batch",
        json={"ids": [invoice1["id"]], "command": "mark_complete"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/invoices/batch",
        json={"ids": [invoice2["id"]], "command": "mark_complete"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert (await client.get(f"/products/{product1['id']}")).json()["quantity"] == -1
    assert (await client.get(f"/products/{product2['id']}")).json()["quantity"] == 4
    assert (
        await client.post("/invoices", json={"price": 1, "store_id": store_id, "products": {product2["id"]: 10}})
    ).status_code == 422  # disallow creating invoice with too much stock


async def test_configurator_dns_resolve(client: TestClient):
    assert (await client.get("/configurator/dns-resolve?name=test")).json() is False
    assert (await client.get("/configurator/dns-resolve?name=example.com")).json() is True


async def test_tfa_flow(client: TestClient, user, token):
    original_token = token
    assert (
        await client.post("/users/2fa/totp/verify", json={"code": "wrong"}, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 422
    resp = await client.post(
        "/users/2fa/totp/verify",
        json={"code": pyotp.TOTP(user["totp_key"]).now()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 10
    recovery_code = resp.json()[0]
    token = (await client.post("/token", json={"email": user["email"], "password": static_data.USER_PWD})).json()
    assert token["tfa_required"] is True
    assert token["tfa_types"] == ["totp"]
    assert (
        await client.post("/token/2fa/totp", json={"token": "wrong", "code": pyotp.TOTP(user["totp_key"]).now()})
    ).status_code == 422
    assert (await client.post("/token/2fa/totp", json={"token": token["tfa_code"], "code": "wrong"})).status_code == 422
    resp = await client.post("/token/2fa/totp", json={"token": token["tfa_code"], "code": pyotp.TOTP(user["totp_key"]).now()})
    assert resp.status_code == 200
    assert resp.json()["tfa_required"] is False
    assert len(resp.json()["access_token"]) == len(original_token)
    assert (
        await client.post("/token/2fa/totp", json={"token": token["tfa_code"], "code": pyotp.TOTP(user["totp_key"]).now()})
    ).status_code == 422
    token = (await client.post("/token", json={"email": user["email"], "password": static_data.USER_PWD})).json()
    assert (await client.post("/token/2fa/totp", json={"token": token["tfa_code"], "code": recovery_code})).status_code == 200
    assert (await client.post("/token/2fa/totp", json={"token": token["tfa_code"], "code": recovery_code})).status_code == 422
    assert (await client.post("/users/2fa/disable", headers={"Authorization": f"Bearer {original_token}"})).status_code == 200
    assert (await client.post("/token", json={"email": user["email"], "password": static_data.USER_PWD})).json()[
        "tfa_required"
    ] is False


async def test_verify_email(client: TestClient, user, token, mocker):
    assert user["is_verified"] is False
    auth_code = None

    def func(url, code):
        nonlocal auth_code
        auth_code = code

    mocker.patch("api.utils.email.Email.is_enabled", return_value=True)
    mocker.patch("api.utils.email.Email.send_mail", return_value=True)
    mocker.patch("api.utils.routing.get_redirect_url", side_effect=func)
    assert (
        await client.post("/users/verify", json={"email": "notexisting@gmail.com", "next_url": "https://example.com"})
    ).status_code == 200
    assert (
        await client.post("/users/verify", json={"email": user["email"], "next_url": "https://example.com"})
    ).status_code == 200
    assert auth_code is not None
    assert (await client.post("/users/verify/finalize/notexisting", json={"password": "12345678"})).status_code == 422
    assert (await client.post(f"/users/verify/finalize/{auth_code}", json={"password": "12345678"})).status_code == 200
    assert (await client.post(f"/users/verify/finalize/{auth_code}", json={"password": "12345678"})).status_code == 422
    assert (await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})).json()["is_verified"] is True
    assert (await client.post("/users/verify", json={"email": user["email"], "next_url": "https://example.com"})).json()[
        "detail"
    ] == "User is already verified"


async def test_token_verification(client: TestClient, user, token):
    assert (
        await client.post("/token", json={"email": "testsuperuser@example.com", "password": static_data.USER_PWD})
    ).status_code == 200
    await client.post(
        "/manage/policies",
        json={"require_verified_email": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert (await client.post("/token", json={"email": "testsuperuser@example.com", "password": static_data.USER_PWD})).json()[
        "detail"
    ] == "Email is not verified"
    assert (
        await client.patch(f"/users/{user['id']}", json={"is_enabled": False}, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200
    assert (await client.post("/token", json={"email": "testsuperuser@example.com", "password": static_data.USER_PWD})).json()[
        "detail"
    ] == "Account is disabled"
    assert (
        await client.patch(f"/users/{user['id']}", json={"is_enabled": True}, headers={"Authorization": f"Bearer {token}"})
    ).json()["detail"] == "Account is disabled"


async def test_reset_password(client: TestClient, token):
    assert (
        await client.post(
            "/users/password",
            json={"old_password": "wrong", "password": "12345678"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 422
    assert (
        await client.post(
            "/users/password",
            json={"old_password": static_data.USER_PWD, "password": "12345678"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert (
        await client.post("/token", json={"email": "testsuperuser@example.com", "password": static_data.USER_PWD})
    ).status_code == 401


async def test_files_functionality(client: TestClient, token, limited_user):
    limited_token = (await create_token(client, limited_user, permissions=["file_management"]))["access_token"]
    resp = await client.post("/files", files={"file": ("test.txt", b"test")}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    file_id = resp.json()["id"]
    stored_fname = f"{file_id}-{resp.json()['filename']}"
    assert os.path.exists(os.path.join(settings.settings.files_dir, stored_fname))
    limited_resp = await client.post(
        "/files", files={"file": ("test.txt", b"test")}, headers={"Authorization": f"Bearer {limited_token}"}
    )
    assert limited_resp.status_code == 200
    limited_file_id = limited_resp.json()["id"]
    assert (
        await client.post("/manage/policies", json={"allow_file_uploads": False}, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200
    assert (
        await client.post(
            "/files", files={"file": ("test.txt", b"test")}, headers={"Authorization": f"Bearer {limited_token}"}
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/files/{limited_file_id}",
            files={"file": ("test.txt", b"test")},
            headers={"Authorization": f"Bearer {limited_token}"},
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/files/{file_id}", files={"file": ("test2.txt", b"test2")}, headers={"Authorization": f"Bearer {token}"}
        )
    ).status_code == 200
    assert not os.path.exists(os.path.join(settings.settings.files_dir, stored_fname))
    stored_fname = f"{file_id}-test2.txt"
    assert os.path.exists(os.path.join(settings.settings.files_dir, stored_fname))
    assert (
        await client.get(f"/files/handle/{file_id}")
    ).next_request.url == f"http://testserver/files/localstorage/{stored_fname}"
    assert (await client.delete(f"/files/{file_id}", headers={"Authorization": f"Bearer {token}"})).status_code == 200
    assert not os.path.exists(os.path.join(settings.settings.files_dir, stored_fname))
    assert (
        await client.post(
            "/files/batch",
            json={"command": "delete", "ids": [limited_file_id]},
            headers={"Authorization": f"Bearer {limited_token}"},
        )
    ).status_code == 200
    assert not os.path.exists(os.path.join(settings.settings.files_dir, f"{limited_file_id}-test.txt"))


async def test_generate_wallet(client: TestClient, token):
    resp1 = await client.post(
        "/wallets/create", json={"currency": "btc", "hot_wallet": True}, headers={"Authorization": f"Bearer {token}"}
    )
    resp2 = await client.post(
        "/wallets/create", json={"currency": "btc", "hot_wallet": False}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert len(resp1.json()["seed"].split()) == len(resp2.json()["seed"].split()) == 12
    assert resp1.json()["seed"] == resp1.json()["key"]
    assert resp2.json()["key"].startswith("vpub")


async def test_refund_functionality(client: TestClient, user, token, mocker):
    invoice = await create_invoice(client, user["id"], token, buyer_email="test@test.com")
    invoice_id = invoice["id"]
    assert (
        await client.post(
            f"/invoices/{invoice_id}/refunds",
            json={"amount": 1, "currency": "USD", "send_email": True, "admin_host": "http://admin"},
        )
    ).status_code == 401
    assert (
        await client.post(
            f"/invoices/{invoice_id}/refunds",
            json={"amount": 1, "currency": "USD", "send_email": True, "admin_host": "http://admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 422  # invoice unpaid
    await invoices.new_payment_handler(DummyInstance(), None, invoice["payments"][0]["lookup_field"], "complete", None)
    full_url = ""

    async def func(store, invoice, refund, refund_url):
        nonlocal full_url
        full_url = refund_url

    mocker.patch("api.utils.email.Email.is_enabled", return_value=True)
    mocker.patch("api.utils.email.Email.send_mail", return_value=True)
    mocker.patch("api.utils.templates.get_customer_refund_template", side_effect=func)
    resp = await client.post(
        f"/invoices/{invoice_id}/refunds",
        json={"amount": 1, "currency": "USD", "send_email": True, "admin_host": "http://admin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    refund_id = resp.json()["id"]
    assert full_url == f"http://admin/refunds/{refund_id}"
    assert (await client.get(f"/invoices/refunds/{refund_id}")).json() == resp.json()
    # submit refund address
    assert (
        await client.post(f"/invoices/refunds/{refund_id}/submit", json={"destination": "test"})
    ).status_code == 422  # address validation
    resp2 = await client.post(f"/invoices/refunds/{refund_id}/submit", json={"destination": static_data.PAYOUT_DESTINATION})
    assert resp2.status_code == 200
    assert (
        await client.post(f"/invoices/refunds/{refund_id}/submit", json={"destination": static_data.PAYOUT_DESTINATION})
    ).status_code == 422  # already submitted
    assert (await client.get(f"/invoices/refunds/{refund_id}")).json() == resp2.json()
    assert resp2.json()["payout_status"] == "pending"
    assert resp2.json()["tx_hash"] is None
    assert resp2.json()["wallet_currency"] == "btc"
    payout = await models.Payout.get((await models.Refund.get(refund_id)).payout_id)
    await payout.update(tx_hash="test").apply()
    await payouts.update_status(payout, payouts.PayoutStatus.SENT)
    invoice = (await client.get(f"/invoices/{invoice_id}")).json()
    assert invoice["status"] == "refunded"
    resp2 = await client.get(f"/invoices/refunds/{refund_id}")
    assert resp2.json()["payout_status"] == "sent"
    assert resp2.json()["tx_hash"] == "test"
