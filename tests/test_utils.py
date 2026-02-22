from __future__ import annotations

import asyncio
import contextlib
import os
import pathlib
import shlex
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

import pytest
import pytest_mock
from bitcart.errors import BaseError as BitcartBaseError
from dishka import Scope
from fastapi import FastAPI, HTTPException

from api import exceptions, models, utils
from api.constants import TFA_RECOVERY_ALPHABET
from api.schemas.misc import CaptchaType
from api.schemas.wallets import DisplayWallet
from api.services.auth import AuthService
from api.services.crud.stores import StoreService
from api.services.crud.templates import TemplateService
from api.services.management import ManagementService
from api.services.notification_manager import NotificationManager
from api.services.wallet_data import WalletDataService
from api.settings import Settings
from api.types import PasswordHasherProtocol, StrEnum
from tests.helper import create_notification, create_store, enabled_logs

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

# https://docs.hcaptcha.com/#integration-testing-test-keys
# https://developers.cloudflare.com/turnstile/reference/testing
VALID_CAPTCHA = {
    CaptchaType.HCAPTCHA: {
        "API": "https://hcaptcha.com/siteverify",
        "CODE": "20000000-aaaa-bbbb-cccc-000000000002",
        "SECRET": "0x0000000000000000000000000000000000000000",
    },
    CaptchaType.CF_TURNSTILE: {
        "API": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        "CODE": "1x00000000000000000000AA",
        "SECRET": "1x0000000000000000000000000000000AA",
    },
}


@pytest.fixture
async def password_hasher(app: FastAPI) -> PasswordHasherProtocol:
    return await app.state.dishka_container.get(PasswordHasherProtocol)


def test_verify_password(password_hasher: PasswordHasherProtocol) -> None:
    p_hash = password_hasher.get_password_hash("12345")
    assert isinstance(p_hash, str)
    assert password_hasher.verify_password("12345", p_hash)


@dataclass
class MockTemplateObj:
    template_name: str
    create_id: str = "1"
    mock_name: str = "MockTemplateObj"
    user_id: str = "1"
    id: str = "1"

    @property
    def templates(self) -> dict[str, str]:
        return {self.template_name: self.create_id}

    def __str__(self) -> str:
        return self.mock_name


@dataclass
class MockStore:
    user_id: str = "1"

    def __str__(self) -> str:
        return "MockStore"


@pytest.mark.anyio
async def test_get_template(
    notification_template: str, client: TestClient, token: str, user: dict[str, Any], app: FastAPI
) -> None:
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template = await template_service.get_template("notification")
    assert template.name == "notification"
    assert template.template_text == notification_template
    assert template.render() == ""
    with pytest.raises(exceptions.TemplateDoesNotExistError):
        async with app.state.dishka_container(scope=Scope.REQUEST) as container:
            template_service = await container.get(TemplateService)
            await template_service.get_template("templ")
    resp = await client.post(
        "/templates",
        json={"name": "templ", "text": "Hello {{var1}}!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template_id = resp.json()["id"]
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template2 = await template_service.get_template("templ", user_id=user["id"])
    assert template2.name == "templ"
    assert template2.template_text == "Hello {{var1}}!"
    assert template2.render() == "Hello !"
    assert template2.render(var1="world") == "Hello world!"
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template3 = await template_service.get_template(
            "notification", obj=MockTemplateObj(template_name="notification", create_id=template_id)
        )
    assert template3.name == "notification"
    assert template3.template_text == template2.template_text


@pytest.mark.anyio
async def test_product_template(client: TestClient, token: str, user: dict[str, Any], app: FastAPI) -> None:
    qty = 10
    product_template = MockTemplateObj(template_name="product", mock_name="MockProduct")
    store = MockStore(user_id=user["id"])
    # default product template
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template = await template_service.get_product_template(store, product_template, qty)
    assert template == f"Thanks for buying  x {qty}!\nIt'll ship shortly!\n"
    # custom template
    resp = await client.post(
        "/templates",
        json={"name": "product", "text": "store={{store}}|product={{product}}|quantity={{quantity}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template_id = resp.json()["id"]
    # Required for unique id
    product_template.create_id = template_id
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template = await template_service.get_product_template(store, product_template, qty)
    assert template == f"store={store}|product={product_template}|quantity={qty}"


@pytest.mark.anyio
async def test_store_template(client: TestClient, token: str, user: dict[str, Any], app: FastAPI) -> None:
    shop = MockTemplateObj(template_name="shop", mock_name="MockShop", user_id=user["id"])
    product = "my product"
    # default store template
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template = await template_service.get_store_template(shop, [product])
    assert template.startswith("Welcome to our shop")
    # custom template
    resp = await client.post(
        "/templates",
        json={"name": "shop", "text": "store={{store}}|products={{products}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template_id = resp.json()["id"]
    shop.create_id = template_id
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template = await template_service.get_store_template(shop, product)
    assert template == f"store={shop}|products={product}"


@pytest.mark.anyio
async def test_notification_template(client: TestClient, token: str, user: dict[str, Any], app: FastAPI) -> None:
    invoice = "my invoice"
    notification = MockTemplateObj(template_name="notification", mock_name="MockNotification", user_id=user["id"])
    # default notification template
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template = await template_service.get_notify_template(notification, invoice)
    assert template.strip() == "New order from  for  !"
    # custom template
    resp = await client.post(
        "/templates",
        json={"name": "notification", "text": "store={{store}}|invoice={{invoice}}"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    template_id = resp.json()["id"]
    notification.create_id = template_id
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        template_service = await container.get(TemplateService)
        template = await template_service.get_notify_template(notification, invoice)
    assert template == f"store={notification}|invoice={invoice}"


# NOTE: this only works because those methods don't call any session-based objects
@pytest.fixture
async def management_service(app: FastAPI) -> ManagementService:
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        return await container.get(ManagementService)


@pytest.mark.anyio
def test_run_host(mocker: pytest_mock.MockerFixture, management_service: ManagementService) -> None:
    test_file = os.path.expanduser("~/test-output")
    with contextlib.suppress(OSError):  # prepare for test
        os.remove(test_file)
    content = f"touch {test_file}"
    # No valid ssh connection
    ok, error = management_service.run_host(content)
    assert ok is False
    assert not os.path.exists(test_file)
    assert "Connection problem" in cast(str, error)
    assert management_service.run_host_output(content, "good")["status"] == "error"
    # Same with key file
    management_service.settings.ssh_settings.key_file = "something"
    assert management_service.run_host(content)[0] is False
    assert not os.path.exists(test_file)
    management_service.settings.ssh_settings.key_file = ""
    mocker.patch("paramiko.SSHClient.connect", return_value=True)
    mocker.patch(
        "paramiko.SSHClient.exec_command",
        side_effect=lambda command: subprocess.run(shlex.split(command), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
    )
    ok, error = management_service.run_host(content)
    assert ok is True
    assert error is None
    assert management_service.run_host_output(content, "good") == {"status": "success", "message": "good"}
    time.sleep(1)  # wait for command to execute (non-blocking)
    assert os.path.exists(test_file)
    os.remove(test_file)  # Cleanup


def test_parse_log_date(settings: Settings, management_service: ManagementService) -> None:
    with enabled_logs(settings):
        assert management_service._parse_log_date("bitcart20210821.log") == datetime(2021, 8, 21)
        assert management_service._parse_log_date("bitcart20250210.log") == datetime(2025, 2, 10)
        assert management_service._parse_log_date("bitcart.log") is None  # current log, no date
        assert management_service._parse_log_date("other20210821.log") is None  # wrong prefix
        assert management_service._parse_log_date("bitcartinvalid.log") is None  # invalid date
    assert management_service._parse_log_date("bitcart20210821.log") is None


@pytest.mark.anyio
async def test_cleanup_old_logs(settings: Settings, management_service: ManagementService, tmp_path: pathlib.Path) -> None:
    log_dir = str(tmp_path / "logs")
    os.makedirs(log_dir)
    current_log = os.path.join(log_dir, "bitcart.log")
    old_log = os.path.join(log_dir, "bitcart20200101.log")
    recent_log = os.path.join(log_dir, "bitcart99991231.log")
    for f in [current_log, old_log, recent_log]:
        with open(f, "w") as fh:  # noqa: ASYNC230
            fh.write("test\n")
    with enabled_logs(settings, datadir=str(tmp_path)):
        # Cleanup with 90-day retention should remove old log but keep recent one
        await management_service.cleanup_old_logs(90)
        assert not os.path.exists(old_log)
        assert os.path.exists(recent_log)
        # Current log file (bitcart.log) should never be touched
        assert os.path.exists(current_log)


def test_versiontuple() -> None:
    assert utils.common.versiontuple("1.2.3") == (1, 2, 3)
    assert utils.common.versiontuple("0.6.0.0") == (0, 6, 0, 0)
    with pytest.raises(ValueError):
        utils.common.versiontuple("0.6.0.0dev")  # not supported for now


@pytest.mark.anyio
async def test_custom_create_task(caplog: pytest.LogCaptureFixture) -> None:
    err_msg = "Test exception"

    async def task() -> None:
        raise Exception(err_msg)

    utils.tasks.create_task(task())
    await asyncio.sleep(1)
    assert err_msg in caplog.text
    caplog.clear()
    utils.tasks.create_task(task()).cancel()
    await asyncio.sleep(1)
    assert err_msg not in caplog.text


@pytest.mark.anyio
async def test_no_exchange_rates_available(
    mocker: pytest_mock.MockerFixture, caplog: pytest.LogCaptureFixture, wallet: dict[str, Any], app: FastAPI
) -> None:
    wallet_data_service = await app.state.dishka_container.get(WalletDataService)
    mocker.patch(
        "api.services.exchange_rate.ExchangeRateService.get_rate", side_effect=BitcartBaseError("No exchange rates available")
    )
    rate = await wallet_data_service.get_rate(DisplayWallet(**wallet), "USD")
    assert rate == Decimal(1)
    assert "Error fetching rates" in caplog.text


@pytest.mark.anyio
async def test_broken_coin(
    mocker: pytest_mock.MockerFixture, caplog: pytest.LogCaptureFixture, wallet: dict[str, Any], app: FastAPI
) -> None:
    wallet_data_service = await app.state.dishka_container.get(WalletDataService)
    mocker.patch("bitcart.BTC.balance", side_effect=BitcartBaseError("Coin broken"))
    success, divisibility, balance = await wallet_data_service.get_confirmed_wallet_balance(DisplayWallet(**wallet))
    assert not success
    assert divisibility == 8
    assert balance == Decimal(0)
    assert "Error getting wallet balance" in caplog.text


def test_search_query_parsing() -> None:
    q1 = utils.common.SearchQuery("text")
    assert q1.text == "text"
    assert q1.filters == {}
    q2 = utils.common.SearchQuery(
        'column:value column:value2 text column2:value2 text2 column3:other:value column2:value3 "column3:other:value"'
    )
    assert q2.text == "text text2 column3:other:value"
    assert q2.filters == {"column": ["value", "value2"], "column2": ["value2", "value3"], "column3": ["other:value"]}


def test_search_query_metadata_parsing() -> None:
    q1 = utils.common.SearchQuery("metadata.external_id:abc123")
    assert q1.metadata_filters == {"external_id": ["abc123"]}
    assert q1.filters == {}
    assert q1.text == ""
    q2 = utils.common.SearchQuery("metadata.external_id:abc123 status:complete")
    assert q2.metadata_filters == {"external_id": ["abc123"]}
    assert q2.filters == {"status": ["complete"]}
    assert q2.text == ""
    q3 = utils.common.SearchQuery("metadata.external_id:abc123 metadata.external_id:abc124 status:complete status:pending")
    assert q3.metadata_filters == {"external_id": ["abc123", "abc124"]}
    assert q3.filters == {"status": ["complete", "pending"]}
    assert q3.text == ""


def check_date(date: datetime | None, **kwargs: int) -> None:
    now = utils.time.now()
    assert now - cast(datetime, date) >= timedelta(**kwargs)


def test_search_query_parse_datetime() -> None:
    assert utils.common.SearchQuery("start_date:-1").parse_datetime("start_date") is None
    assert utils.common.SearchQuery("start_date:-testd").parse_datetime("start_date") is None
    check_date(utils.common.SearchQuery("start_date:-1d").parse_datetime("start_date"), days=1)
    check_date(utils.common.SearchQuery("end_date:-1d").parse_datetime("end_date"), days=1)
    check_date(utils.common.SearchQuery("start_date:-1h").parse_datetime("start_date"), hours=1)
    check_date(utils.common.SearchQuery("start_date:-1w").parse_datetime("start_date"), weeks=1)
    check_date(utils.common.SearchQuery("start_date:-1m").parse_datetime("start_date"), days=30)
    check_date(utils.common.SearchQuery("start_date:-1y").parse_datetime("start_date"), days=30 * 12)
    check_date(utils.common.SearchQuery("start_date:-150d").parse_datetime("start_date"), days=150)
    assert utils.common.SearchQuery("start_date:2024-01-15").parse_datetime("start_date") == datetime(2024, 1, 15)
    assert utils.common.SearchQuery("start_date:2024-01-15T12:30:00").parse_datetime("start_date") == datetime(
        2024, 1, 15, 12, 30, 0
    )
    assert utils.common.SearchQuery("start_date:2024-01-15T12:30:00+00:00").parse_datetime("start_date") == datetime(
        2024, 1, 15, 12, 30, 0, tzinfo=UTC
    )
    assert utils.common.SearchQuery("start_date:2024-01-15T12:30:00Z").parse_datetime("start_date") == datetime(
        2024, 1, 15, 12, 30, 0, tzinfo=UTC
    )
    assert utils.common.SearchQuery("start_date:2026-02-02T21:00:00.000Z").parse_datetime("start_date") == datetime(
        2026, 2, 2, 21, 0, 0, tzinfo=UTC
    )
    assert utils.common.SearchQuery("start_date:notadate").parse_datetime("start_date") is None
    assert utils.common.SearchQuery("start_date:2024-13-01").parse_datetime("start_date") is None


async def check_modify_notify(
    notification_manager: NotificationManager,
    client: TestClient,
    store: models.Store,
    notification_id: str,
    token: str,
    base_data: dict[str, Any],
    key: str,
    value: Any,
    convert: Callable[[Any], Any],
) -> None:
    assert (
        await client.patch(
            f"/notifications/{notification_id}",
            json={"data": {**base_data, key: value}},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert await notification_manager.notify(store, "Text") is True
    # run only if conversion works
    try:
        converted = convert(value)
        assert (
            await client.patch(
                f"/notifications/{notification_id}",
                json={"data": {**base_data, key: converted}},
                headers={"Authorization": f"Bearer {token}"},
            )
        ).status_code == 200
        await notification_manager.notify(store, "Text")
    except Exception:
        pass


@pytest.mark.anyio
async def test_send_notification(client: TestClient, token: str, mocker: pytest_mock.MockerFixture, app: FastAPI) -> None:
    notification_manager = await app.state.dishka_container.get(NotificationManager)
    mocker.patch("apprise.plugins.matrix.NotifyMatrix.send", return_value=True)
    notification = await create_notification(client, token, data={"user_id": 5})
    notification_id = notification["id"]
    data = await create_store(client, token, custom_store_attrs={"notifications": [notification_id]})
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        store_service = await container.get(StoreService)
        store = await store_service.get_or_none(data["id"])
    resp = await client.patch(
        f"/notifications/{notification_id}",
        json={"provider": "Telegram"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == notification["data"]
    resp2 = await client.patch(
        f"/notifications/{notification_id}",
        json={"provider": "Matrix"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["provider"] == "Matrix"
    assert resp2.json()["data"] == {}
    assert await notification_manager.notify(store, "Text") is False
    base_data = {"host": "matrix.org"}
    assert (
        await client.patch(
            f"/notifications/{notification_id}",
            json={"data": base_data},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).status_code == 200
    assert await notification_manager.notify(store, "Text") is True
    # Test that some primitive types are automatically converted
    await check_modify_notify(notification_manager, client, store, notification_id, token, base_data, "verify", "test", bool)
    await check_modify_notify(notification_manager, client, store, notification_id, token, base_data, "verify", "true", bool)
    await check_modify_notify(notification_manager, client, store, notification_id, token, base_data, "verify", True, bool)
    await check_modify_notify(notification_manager, client, store, notification_id, token, base_data, "port", "5", int)
    await check_modify_notify(notification_manager, client, store, notification_id, token, base_data, "port", "test", int)
    await check_modify_notify(notification_manager, client, store, notification_id, token, base_data, "rto", "5.5", int)
    await check_modify_notify(notification_manager, client, store, notification_id, token, base_data, "rto", "test", int)


@pytest.mark.anyio
async def test_run_universal() -> None:
    def func(arg: int) -> int:
        return arg

    async def async_func(arg: int) -> int:
        return arg

    assert await utils.common.run_universal(func, 5) == await utils.common.run_universal(async_func, 5) == 5


def test_get_redirect_url() -> None:
    assert utils.routing.get_redirect_url("https://example.com", code="test") == "https://example.com?code=test"
    assert utils.routing.get_redirect_url("https://example.com?code=1", code="test") == "https://example.com?code=1&code=test"


def test_gen_recovery_code() -> None:
    code = utils.authorization.generate_tfa_recovery_code()
    assert len(code) == 11
    assert code[5] == "-"
    assert all(x in TFA_RECOVERY_ALPHABET for x in code[:5])
    assert all(x in TFA_RECOVERY_ALPHABET for x in code[6:])


def test_str_enum() -> None:
    class TestEnum(StrEnum):
        TEST = "test"
        TEST2 = "test2"

    assert TestEnum.TEST == "test"
    assert TestEnum.TEST2 == "test2"

    assert list(TestEnum) == ["test", "test2"]
    assert "test" in TestEnum
    assert "test2" in TestEnum
    assert "test3" not in TestEnum


@pytest.mark.anyio
@pytest.mark.parametrize("impl", [CaptchaType.HCAPTCHA, CaptchaType.CF_TURNSTILE])
async def test_verify_captcha(impl: CaptchaType, app: FastAPI) -> None:
    details = VALID_CAPTCHA[cast(str, impl)]
    # Test with valid code & secret
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        auth_service = await container.get(AuthService)
        assert await auth_service.verify_captcha(details["API"], code=details["CODE"], secret=details["SECRET"])

    # Test with invalid code/secret
    if str(impl) == CaptchaType.CF_TURNSTILE:
        async with app.state.dishka_container(scope=Scope.REQUEST) as container:
            auth_service = await container.get(AuthService)
            assert await auth_service.verify_captcha(
                details["API"], code="non-valid-code", secret=details["SECRET"]
            )  # secret takes precedence
    else:
        async with app.state.dishka_container(scope=Scope.REQUEST) as container:
            auth_service = await container.get(AuthService)
            assert not await auth_service.verify_captcha(details["API"], code="non-valid-code", secret=details["SECRET"])
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        auth_service = await container.get(AuthService)
        assert not await auth_service.verify_captcha(details["API"], code=details["CODE"], secret="non-valid-secret")


@pytest.mark.anyio
@pytest.mark.parametrize("impl", [CaptchaType.HCAPTCHA, CaptchaType.CF_TURNSTILE])
async def test_captcha_flow(mocker: pytest_mock.MockerFixture, impl: CaptchaType, app: FastAPI) -> None:
    fake_run_hook = mocker.patch("api.services.plugin_registry.PluginRegistry.run_hook")

    fake_policy = mocker.Mock()
    fake_policy.captcha_secretkey = VALID_CAPTCHA[cast(str, impl)]["SECRET"]
    fake_policy.captcha_type = impl
    mocker.patch("api.services.settings.SettingService.get_setting", return_value=fake_policy)
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        auth_service = await container.get(AuthService)
        await auth_service.captcha_flow(VALID_CAPTCHA[cast(str, impl)]["CODE"])
    fake_run_hook.assert_called_once_with("captcha_passed")

    fake_run_hook.reset_mock()
    fake_policy.captcha_secretkey = "non-valid-secret"
    with pytest.raises(HTTPException):
        async with app.state.dishka_container(scope=Scope.REQUEST) as container:
            auth_service = await container.get(AuthService)
            await auth_service.captcha_flow("invalid-code")
    fake_run_hook.assert_called_once_with("captcha_failed")
