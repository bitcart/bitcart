from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

import pytest
import pytest_mock
from aiohttp import web
from aiohttp.test_utils import TestServer
from dishka import Scope
from fastapi import FastAPI, HTTPException

from api.constants import CAPTCHA_TIMEOUT, CaptchaAction
from api.schemas.misc import CaptchaType
from api.services.auth import CAPTCHA_URLS, AuthService
from tests.fixtures import static_data
from tests.helper import allow_outbound, create_user

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

pytestmark = pytest.mark.anyio

PROVIDERS = [CaptchaType.HCAPTCHA, CaptchaType.CF_TURNSTILE]


class FakeProvider:
    def __init__(self) -> None:
        self.requests: list[dict[str, str]] = []
        self.status = 200
        self.delay = 0.0
        self.result: Any = {"success": True, "action": "login"}

    async def verify(self, request: web.Request) -> web.Response:
        self.requests.append({key: str(value) for key, value in (await request.post()).items()})
        await asyncio.sleep(self.delay)
        return web.json_response(self.result, status=self.status)


@pytest.fixture
async def provider(mocker: pytest_mock.MockerFixture) -> AsyncIterator[FakeProvider]:
    fake = FakeProvider()
    web_app = web.Application()
    web_app.router.add_post("/siteverify", fake.verify)
    allow_outbound(mocker, "127.0.0.1")
    async with TestServer(web_app, host="127.0.0.1") as server:
        mocker.patch.dict(CAPTCHA_URLS, dict.fromkeys(PROVIDERS, str(server.make_url("/siteverify"))))
        yield fake


@pytest.fixture
def run_hook(mocker: pytest_mock.MockerFixture) -> Any:
    return mocker.patch("api.services.plugin_registry.PluginRegistry.run_hook")


@pytest.fixture
def logger(mocker: pytest_mock.MockerFixture) -> Any:
    return mocker.patch("api.services.auth.logger")


async def check_captcha(
    app: FastAPI, mocker: pytest_mock.MockerFixture, captcha_type: str, code: str | None = "code", **kwargs: Any
) -> None:
    policy = mocker.Mock(captcha_type=captcha_type, captcha_secretkey="secret", captcha_sitekey="sitekey")
    mocker.patch("api.services.settings.SettingService.get_setting", return_value=policy)
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        await (await container.get(AuthService)).captcha_flow(code, CaptchaAction.LOGIN, **kwargs)


def test_providers_urls() -> None:
    assert CAPTCHA_URLS == {
        "hcaptcha": "https://api.hcaptcha.com/siteverify",
        "cloudflare_turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    }


@pytest.mark.parametrize(
    "captcha_type,sent",
    [
        (CaptchaType.HCAPTCHA, {"response": "code", "secret": "secret", "sitekey": "sitekey", "remoteip": "203.0.113.5"}),
        (CaptchaType.CF_TURNSTILE, {"response": "code", "secret": "secret", "remoteip": "203.0.113.5"}),
    ],
)
async def test_solved_captcha(
    captcha_type: str,
    sent: dict[str, str],
    app: FastAPI,
    mocker: pytest_mock.MockerFixture,
    provider: FakeProvider,
    run_hook: Any,
) -> None:
    await check_captcha(app, mocker, captcha_type, client_ip="203.0.113.5")
    assert provider.requests == [sent]
    run_hook.assert_called_once_with("captcha_passed")
    await check_captcha(app, mocker, captcha_type)
    assert "remoteip" not in provider.requests[1]


@pytest.mark.parametrize("captcha_type", PROVIDERS)
async def test_rejected_captcha(
    captcha_type: str,
    app: FastAPI,
    mocker: pytest_mock.MockerFixture,
    provider: FakeProvider,
    run_hook: Any,
    logger: Any,
) -> None:
    provider.result = {"success": False, "error-codes": ["invalid-input-response"]}
    with pytest.raises(HTTPException) as e:
        await check_captcha(app, mocker, captcha_type)
    assert e.value.status_code == 401
    run_hook.assert_called_once_with("captcha_failed")
    assert "invalid-input-response" in logger.warning.call_args.args[0]


@pytest.mark.parametrize("action", ["register", "", None])
async def test_turnstile_action_must_match(
    action: str | None, app: FastAPI, mocker: pytest_mock.MockerFixture, provider: FakeProvider, run_hook: Any, logger: Any
) -> None:
    provider.result["action"] = action
    with pytest.raises(HTTPException) as e:
        await check_captcha(app, mocker, CaptchaType.CF_TURNSTILE)
    assert e.value.status_code == 401
    assert "'login'" in logger.warning.call_args.args[0]
    await check_captcha(app, mocker, CaptchaType.HCAPTCHA)


@pytest.mark.parametrize("captcha_type", PROVIDERS)
@pytest.mark.parametrize("status,result", [(500, {"success": True}), (400, "x"), (200, []), (200, {}), (200, "x")])
async def test_provider_failure(
    captcha_type: str,
    status: int,
    result: Any,
    app: FastAPI,
    mocker: pytest_mock.MockerFixture,
    provider: FakeProvider,
    run_hook: Any,
    logger: Any,
) -> None:
    provider.status, provider.result = status, result
    with pytest.raises(HTTPException) as e:
        await check_captcha(app, mocker, captcha_type)
    assert e.value.status_code == 503
    run_hook.assert_not_called()
    assert "is unavailable" in logger.error.call_args.args[0]


async def test_provider_timeout(app: FastAPI, mocker: pytest_mock.MockerFixture, provider: FakeProvider, logger: Any) -> None:
    assert CAPTCHA_TIMEOUT == 10
    mocker.patch("api.services.auth.CAPTCHA_TIMEOUT", 0.1)
    provider.delay = 5
    with pytest.raises(HTTPException) as e:
        await check_captcha(app, mocker, CaptchaType.HCAPTCHA)
    assert e.value.status_code == 503


@pytest.mark.parametrize("code", ["", None])
async def test_missing_code_is_rejected_without_asking_the_provider(
    code: str | None, app: FastAPI, mocker: pytest_mock.MockerFixture, provider: FakeProvider
) -> None:
    with pytest.raises(HTTPException) as e:
        await check_captcha(app, mocker, CaptchaType.HCAPTCHA, code)
    assert e.value.status_code == 401
    assert provider.requests == []


async def test_disabled_captcha(app: FastAPI, mocker: pytest_mock.MockerFixture, provider: FakeProvider) -> None:
    await check_captcha(app, mocker, CaptchaType.NONE, "")
    assert provider.requests == []


async def test_every_form_sends_its_action_and_the_client_ip(
    client: TestClient, user: dict[str, Any], token: str, provider: FakeProvider, mocker: pytest_mock.MockerFixture
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    policy = {"captcha_type": CaptchaType.CF_TURNSTILE, "disable_registration": False}
    assert (await client.post("/manage/policies", json=policy, headers=headers)).status_code == 200
    mocker.patch("api.services.email.EmailService.ensure_deliverable")
    password = {"email": user["email"], "password": "wrong"}
    new_user = {"email": "captcha@bitcart.test", "password": "12345678"}
    forms: list[tuple[str, str, dict[str, Any], int]] = [
        ("/token", "login", password, 401),
        ("/users", "register", new_user, 200),
        ("/users/reset_password", "forgot_password", {"email": user["email"]}, 200),
        ("/users/verify", "verify_email", {"email": user["email"]}, 200),
    ]
    for path, action, body, status in forms:
        provider.result["action"] = "other"
        resp = await client.post(path, json={**body, "captcha_code": "code"})
        assert resp.json()["detail"] == {"message": "Unauthorized", "status": 403}
        provider.result["action"] = action
        resp = await client.post(path, json={**body, "captcha_code": "code"})
        assert (resp.status_code, resp.json() != {"detail": {"message": "Unauthorized", "status": 403}}) == (status, True)
    client_ip = client._transport.client[0]  # type: ignore[attr-defined]
    assert {request["remoteip"] for request in provider.requests} == {client_ip}
    requests_count = len(provider.requests)
    await create_user(client, token=token, is_superuser=False)
    assert len(provider.requests) == requests_count


async def test_oauth2_login_needs_the_captcha(
    client: TestClient, user: dict[str, Any], token: str, provider: FakeProvider
) -> None:
    policy = {"captcha_type": CaptchaType.CF_TURNSTILE}
    assert (
        await client.post("/manage/policies", json=policy, headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200
    resp = await client.post("/token/oauth2", data={"username": user["email"], "password": static_data.USER_PWD})
    assert (resp.status_code, resp.json()["detail"]) == (401, {"message": "Unauthorized", "status": 403})
