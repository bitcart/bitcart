from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import ssl
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import aiohttp
import pytest
import pytest_mock
from aiohttp import ClientTimeout, web
from aiohttp.test_utils import TestServer
from dishka import Scope
from outbound_guard import OutboundDenied

from api import models, utils
from api.db import AsyncSession
from api.exceptions import EmailSendError
from api.ext.ssh import create_ssh_client
from api.schemas.configurator import ConfiguratorSSHSettings
from api.schemas.misc import EmailSettings
from api.schemas.policies import Policy
from api.services.crud.repositories import UserRepository
from api.services.email import EmailService, Mailer
from api.services.ipn_sender import IPNSender
from api.services.outbound import OutboundService
from api.services.payment_processor import PaymentProcessor
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from tests.helper import (
    allow_outbound,
    create_invoice,
    create_product,
    create_store,
    create_token,
    create_user,
    set_allowed_hosts,
)

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient as TestClient
    from httpx import Response

pytestmark = pytest.mark.anyio


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def get_policies(client: TestClient, token: str) -> dict[str, Any]:
    return (await client.get("/manage/policies", headers=auth(token))).json()


async def set_owner_hosts(client: TestClient, token: str, user_id: str, hosts: Any) -> Response:
    return await client.patch(f"/users/{user_id}", json={"allowed_internal_hosts": hosts}, headers=auth(token))


def store_mailer(settings: EmailSettings, owner_hosts: list[str]) -> Mailer:
    return EmailService().for_store(models.Store(email_settings=settings), owner_hosts)


class FakeServer:
    def __init__(self) -> None:
        self.requests: list[str] = []
        self.redirect_to = ""
        self.app = web.Application()
        self.app.router.add_route("*", "/redirect", self.redirect)
        self.app.router.add_route("*", "/{path:.*}", self.ok)

    async def ok(self, request: web.Request) -> web.Response:
        self.requests.append(f"{request.method} {request.path}")
        return web.json_response({"ok": True})

    async def redirect(self, request: web.Request) -> web.Response:
        self.requests.append(f"{request.method} {request.path}")
        raise web.HTTPTemporaryRedirect(self.redirect_to)


type ServerFactory = Callable[[], Awaitable[tuple[FakeServer, int]]]


@pytest.fixture
async def start_server() -> AsyncIterator[ServerFactory]:
    async with contextlib.AsyncExitStack() as stack:

        async def start() -> tuple[FakeServer, int]:
            fake = FakeServer()
            server = await stack.enter_async_context(TestServer(fake.app, host="127.0.0.1"))
            assert server.port
            return fake, server.port

        yield start


@pytest.mark.parametrize(
    "entry", ["10.0.0.0/8", "http://n8n", "*.lan", "n8n:http", "n8n:", "user@n8n", "n8n:99999", "[fd00::5", "n8n/path", ".lan"]
)
async def test_invalid_allowed_host_entries(entry: str, client: TestClient, token: str) -> None:
    resp = await set_allowed_hosts(client, token, ["localhost", entry])
    assert resp.status_code == 422
    assert resp.json()["detail"].startswith(f"Invalid internal host {entry!r}")
    assert (await get_policies(client, token))["allowed_internal_hosts"] == []


@pytest.mark.parametrize("value", [None, "n8n", [1], [None], {"n8n": True}])
async def test_allowed_hosts_are_a_list_of_strings(value: Any, client: TestClient, token: str) -> None:
    assert (await set_allowed_hosts(client, token, value)).status_code == 422


async def test_allowed_hosts_policy_is_for_server_admins_only(client: TestClient, token: str) -> None:
    resp = await set_allowed_hosts(client, token, [" n8n:5678 ", "n8n:5678", "192.168.1.5"])
    assert resp.status_code == 200
    assert resp.json()["allowed_internal_hosts"] == ["n8n:5678", "192.168.1.5"]
    assert (await get_policies(client, token))["allowed_internal_hosts"] == ["n8n:5678", "192.168.1.5"]
    user = await create_user(client, token=token, is_superuser=False)
    limited_token = (await create_token(client, user))["access_token"]
    assert "allowed_internal_hosts" not in (await client.get("/manage/policies")).json()
    assert "allowed_internal_hosts" not in await get_policies(client, limited_token)
    assert (await set_allowed_hosts(client, limited_token, ["evil"])).status_code == 403
    assert (await client.post("/manage/policies", json={"allowed_internal_hosts": ["evil"]})).status_code == 401
    assert (await get_policies(client, token))["allowed_internal_hosts"] == ["n8n:5678", "192.168.1.5"]


@pytest.fixture
async def outbound(app: FastAPI) -> OutboundService:
    return await app.state.dishka_container.get(OutboundService)


async def test_allowed_hosts_policy_applies_immediately(
    client: TestClient, token: str, start_server: ServerFactory, outbound: OutboundService
) -> None:
    server, port = await start_server()
    url = f"http://127.0.0.1:{port}/"
    async with outbound.session() as session:
        for _ in range(2):
            with pytest.raises(aiohttp.ClientOSError):
                await session.get(url)
            await set_allowed_hosts(client, token, [f"127.0.0.1:{port}"])
            async with session.get(url) as response:
                assert response.status == 200
            await set_allowed_hosts(client, token, [])
    assert len(server.requests) == 2


async def test_only_the_service_uses_allowed_hosts(
    client: TestClient, token: str, start_server: ServerFactory, outbound: OutboundService, mocker: pytest_mock.MockerFixture
) -> None:
    read = mocker.spy(SettingService, "get_stored_setting")
    server, port = await start_server()
    await set_allowed_hosts(client, token, ["127.0.0.1", "localhost"])
    await outbound.forget_allowed_hosts()
    read.reset_mock()
    for host in ("127.0.0.1", "localhost"):
        with pytest.raises(aiohttp.ClientOSError):
            await utils.common.send_request("GET", f"http://{host}:{port}/")
    read.assert_not_called()
    assert server.requests == []
    async with outbound.session() as session, session.get(f"http://127.0.0.1:{port}/"):
        read.assert_called_once()


async def test_allowed_hosts_are_read_without_plugins(
    client: TestClient, token: str, outbound: OutboundService, plugin_registry: PluginRegistry
) -> None:
    await set_allowed_hosts(client, token, ["n8n:5678"])
    await outbound.forget_allowed_hosts()
    explorer = AsyncMock(return_value="")
    plugin_registry.register_filter("get_coin_explorer", explorer)
    assert await outbound.get_allowed_hosts() == ["n8n:5678"]
    explorer.assert_not_called()


async def test_allowed_hosts_are_cached(
    client: TestClient, token: str, outbound: OutboundService, mocker: pytest_mock.MockerFixture
) -> None:
    read = mocker.spy(SettingService, "get_stored_setting")
    await set_allowed_hosts(client, token, ["n8n:5678"])
    read.reset_mock()
    for _ in range(2):
        assert await outbound.get_allowed_hosts() == ["n8n:5678"]
    read.assert_called_once()
    assert 0 < await outbound.allowed_hosts.redis.ttl(outbound.allowed_hosts.key) <= 60


async def test_policy_saved_while_loading_is_not_cached_stale(
    client: TestClient, token: str, outbound: OutboundService, mocker: pytest_mock.MockerFixture
) -> None:
    await set_allowed_hosts(client, token, ["old"])
    load_allowed_hosts = outbound.load_allowed_hosts

    async def save_while_loading() -> list[str]:
        hosts = await load_allowed_hosts()
        await set_allowed_hosts(client, token, ["new"])
        return hosts

    mocker.patch.object(outbound, "load_allowed_hosts", save_while_loading)
    assert await outbound.get_allowed_hosts() == ["old"]
    mocker.stopall()
    assert await outbound.get_allowed_hosts() == ["new"]


async def test_failed_policy_save_keeps_the_allowed_hosts(
    client: TestClient, token: str, outbound: OutboundService, mocker: pytest_mock.MockerFixture
) -> None:
    await set_allowed_hosts(client, token, ["kept"])
    assert await outbound.get_allowed_hosts() == ["kept"]
    mocker.patch.object(AsyncSession, "commit", side_effect=OSError("database is down"))
    with pytest.raises(OSError, match="database is down"):
        await set_allowed_hosts(client, token, ["n8n"])
    mocker.stopall()
    assert await outbound.get_allowed_hosts() == ["kept"]
    assert (await get_policies(client, token))["allowed_internal_hosts"] == ["kept"]


async def test_user_allowed_hosts_are_for_server_admins_only(
    client: TestClient, token: str, mocker: pytest_mock.MockerFixture
) -> None:
    user = await create_user(client, token=token, is_superuser=False)
    user_token = (await create_token(client, user))["access_token"]
    resp = await set_owner_hosts(client, token, user["id"], [" smtp:587 ", "smtp:587", "10.0.0.5"])
    assert resp.status_code == 200
    assert resp.json()["allowed_internal_hosts"] == ["smtp:587", "10.0.0.5"]
    resp = await client.patch(f"/users/{user['id']}", json={"is_verified": True}, headers=auth(token))
    assert resp.json()["allowed_internal_hosts"] == ["smtp:587", "10.0.0.5"]
    assert (await set_owner_hosts(client, token, user["id"], ["http://smtp"])).status_code == 422
    assert (await set_owner_hosts(client, token, user["id"], "smtp")).status_code == 422
    assert (await set_owner_hosts(client, user_token, user["id"], ["evil"])).status_code == 403
    assert "allowed_internal_hosts" not in (await client.get("/users/me", headers=auth(user_token))).json()
    resp = await client.post("/users/me/settings", json={"allowed_internal_hosts": ["evil"]}, headers=auth(user_token))
    assert "allowed_internal_hosts" not in resp.json()
    admin_view = (await client.get(f"/users/{user['id']}", headers=auth(token))).json()
    assert admin_view["allowed_internal_hosts"] == ["smtp:587", "10.0.0.5"]
    mocker.patch.object(EmailService, "ensure_deliverable")
    await client.post("/manage/policies", json={"disable_registration": False}, headers=auth(token))
    resp = await client.post(
        "/users",
        json={"email": "signup@bitcart.test", "password": "password12345", "allowed_internal_hosts": ["evil"]},
    )
    assert resp.status_code == 200
    assert "allowed_internal_hosts" not in resp.json()
    signed_up = (await client.get(f"/users/{resp.json()['id']}", headers=auth(token))).json()
    assert signed_up["allowed_internal_hosts"] == []


async def test_store_email_uses_only_the_owner_allowed_hosts(
    client: TestClient, token: str, smtp_server: FakeSMTPServer, outbound: OutboundService
) -> None:
    hosts = [f"localhost:{smtp_server.port}"]
    email_settings = smtp_settings("localhost", smtp_server.port).model_dump()
    owner = await create_user(client, token=token, is_superuser=False)
    owner_token = (await create_token(client, owner))["access_token"]
    other = await create_user(client, token=token, is_superuser=False)
    other_token = (await create_token(client, other))["access_token"]
    owner_store = await create_store(client, owner_token, {"email_settings": email_settings})
    other_store = await create_store(client, other_token, {"email_settings": email_settings})

    async def ping(store: dict[str, Any], store_token: str) -> bool:
        return (await client.get(f"/stores/{store['id']}/ping", headers=auth(store_token))).json()

    await set_allowed_hosts(client, token, hosts)
    assert not await ping(owner_store, owner_token)
    assert smtp_server.commands == []
    await set_allowed_hosts(client, token, [])
    await set_owner_hosts(client, token, owner["id"], hosts)
    assert await ping(owner_store, owner_token)
    assert not await ping(other_store, other_token)
    async with outbound.session() as session:
        with pytest.raises(aiohttp.ClientOSError):
            await session.get(f"http://localhost:{smtp_server.port}/")
    await set_owner_hosts(client, token, owner["id"], [])
    assert not await ping(owner_store, owner_token)


class PaymentDaemon:
    coin_name = "BTC"
    is_eth_based = False


async def test_buyer_emails_use_the_owner_allowed_hosts(
    client: TestClient, token: str, smtp_server: FakeSMTPServer, app: FastAPI
) -> None:
    payment_processor = await app.state.dishka_container.get(PaymentProcessor)
    me = (await client.get("/users/me", headers=auth(token))).json()
    await set_owner_hosts(client, token, me["id"], [f"localhost:{smtp_server.port}"])
    email_settings = smtp_settings("localhost", smtp_server.port).model_dump()
    store = await create_store(client, token, {"email_settings": email_settings})
    product = await create_product(client, token, store_id=store["id"])
    invoice = await create_invoice(client, token, store_id=store["id"], products=[product["id"]], buyer_email="b@test.com")
    lookup_field = invoice["payments"][0]["lookup_field"]
    await payment_processor.new_payment_handler(PaymentDaemon(), None, lookup_field, "complete", None)
    assert smtp_server.commands.count("DATA") == 1
    resp = await client.post(
        f"/invoices/{invoice['id']}/refunds",
        json={"amount": 1, "currency": "USD", "send_email": True},
        headers=auth(token),
    )
    assert resp.status_code == 200
    assert smtp_server.commands.count("DATA") == 2


async def test_owner_allowed_hosts_of_missing_owners_are_empty(app: FastAPI) -> None:
    async with app.state.dishka_container(scope=Scope.REQUEST) as container:
        user_repository = await container.get(UserRepository)
        assert await user_repository.get_allowed_internal_hosts(None) == []
        assert await user_repository.get_allowed_internal_hosts("missing") == []


async def test_server_email_does_not_need_allowed_hosts(client: TestClient, token: str, smtp_server: FakeSMTPServer) -> None:
    email_settings = smtp_settings("localhost", smtp_server.port).model_dump()
    headers = auth(token)
    store = await create_store(client, token, {"email_settings": email_settings})
    assert (await client.get(f"/stores/{store['id']}/ping", headers=headers)).json() is False
    assert smtp_server.commands == []
    await client.post("/manage/policies", json={"email_settings": email_settings}, headers=headers)
    assert (await client.get("/manage/testping", headers=headers)).json() is True
    assert (await client.get(f"/stores/{store['id']}/ping", headers=headers)).json() is False


async def test_server_email_times_out(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("api.services.email.SMTP_TIMEOUT", 0.05)
    mocker.patch("api.services.email.socket.create_connection", lambda *_: time.sleep(0.5))
    started = time.monotonic()
    mailer = EmailService().for_server(Policy(email_settings=smtp_settings("smtp.example.com", 25)))
    assert not await mailer.check_ping()
    assert time.monotonic() - started < 0.4


async def test_configurator_does_not_use_allowed_hosts(
    client: TestClient, token: str, mocker: pytest_mock.MockerFixture
) -> None:
    ssh_connect = mocker.patch("paramiko.SSHClient.connect")
    await set_allowed_hosts(client, token, ["localhost", "127.0.0.1"])
    for host in ("localhost", "127.0.0.1"):
        for headers in ({}, {"Authorization": f"Bearer {token}"}):
            resp = await client.post("/configurator/server-settings", json={"host": host}, headers=headers)
            assert resp.status_code == 422
            assert (await client.get(f"/configurator/dns-resolve?name={host}", headers=headers)).json() is False
        with pytest.raises(OutboundDenied):
            await create_ssh_client(ConfiguratorSSHSettings(host=host))
    ssh_connect.assert_not_called()


async def test_denials_name_the_list_to_edit(
    start_server: ServerFactory, outbound: OutboundService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, "outbound_guard")
    _, port = await start_server()
    with pytest.raises(aiohttp.ClientOSError):
        await utils.common.send_request("GET", f"http://localhost:{port}/")
    assert f"localhost:{port}" in caplog.text
    assert "allowed_internal_hosts" not in caplog.text
    async with outbound.session() as session:
        with pytest.raises(aiohttp.ClientOSError) as e:
            await session.get(f"http://localhost:{port}/")
    assert "allowed_internal_hosts" in caplog.text
    assert "allowed_internal_hosts" not in str(e.value)
    with pytest.raises(EmailSendError) as email_error:
        await store_mailer(smtp_settings("localhost", port), []).send("buyer@example.com", "subject", "body")
    assert "store owner's allowed internal hosts" in caplog.text
    assert "allowed internal hosts" not in str(email_error.value)


async def test_send_request_contract(start_server: ServerFactory, mocker: pytest_mock.MockerFixture) -> None:
    _, port = await start_server()
    allow_outbound(mocker, "127.0.0.1")
    url = f"http://127.0.0.1:{port}/"
    assert await utils.common.send_request("GET", url) == {"ok": True}
    response, text = await utils.common.send_request("GET", url, return_json=False, timeout=ClientTimeout(total=10))
    assert response.status == 200
    assert json.loads(text) == await response.json() == {"ok": True}


@dataclass
class Payable:
    notification_url: str
    id: str = "id"


async def test_ipn_does_not_follow_redirects(
    start_server: ServerFactory,
    mocker: pytest_mock.MockerFixture,
    plugin_registry: PluginRegistry,
    outbound: OutboundService,
    client: TestClient,
    token: str,
) -> None:
    logger = mocker.patch("api.services.ipn_sender.logger")
    server, port = await start_server()
    sender = IPNSender(plugin_registry, outbound)
    await sender.send_invoice_ipn(Payable(f"http://127.0.0.1:{port}/ipn"), "paid")
    assert "error" in logger.info.call_args.args[0]
    assert server.requests == []
    await set_allowed_hosts(client, token, ["127.0.0.1"])
    await sender.send_invoice_ipn(Payable(f"http://127.0.0.1:{port}/ipn"), "paid")
    assert "success" in logger.info.call_args.args[0]
    server.redirect_to = f"http://127.0.0.1:{port}/final"
    await sender.send_invoice_ipn(Payable(f"http://127.0.0.1:{port}/redirect"), "paid")
    assert "redirects are not followed" in logger.info.call_args.args[0]
    assert server.requests == ["POST /ipn", "POST /redirect"]


class FakeSMTPServer:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.port = 0

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 ready\r\n")
        while line := (await reader.readline()).decode().strip():
            self.commands.append(line.split()[0].upper())
            match self.commands[-1]:
                case "EHLO":
                    writer.write(b"250-smtp\r\n250 AUTH PLAIN\r\n")
                case "AUTH":
                    writer.write(b"235 ok\r\n")
                case "DATA":
                    writer.write(b"354 go ahead\r\n")
                    await reader.readuntil(b"\r\n.\r\n")
                    writer.write(b"250 ok\r\n")
                case _:
                    writer.write(b"250 ok\r\n")
        writer.close()


@pytest.fixture
async def smtp_server() -> AsyncIterator[FakeSMTPServer]:
    fake = FakeSMTPServer()
    server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
    fake.port = server.sockets[0].getsockname()[1]
    yield fake
    server.close()


def smtp_settings(host: str, port: int, auth_mode: str = "none") -> EmailSettings:
    return EmailSettings(
        address="test@example.com", host=host, port=port, user="user", password="password", auth_mode=auth_mode
    )


async def test_smtp_connects_only_to_checked_addresses(smtp_server: FakeSMTPServer) -> None:
    for host in ("127.0.0.1", "localhost", "127.1", "2130706433"):
        assert not await store_mailer(smtp_settings(host, smtp_server.port), []).check_ping()
    assert smtp_server.commands == []
    assert await store_mailer(smtp_settings("localhost", smtp_server.port), [f"localhost:{smtp_server.port}"]).check_ping()
    assert "VRFY" in smtp_server.commands


async def test_smtp_keeps_the_hostname_for_tls() -> None:
    server_names: list[str | None] = []
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.sni_callback = lambda _, name, __: server_names.append(name)
    server = await asyncio.start_server(lambda _, writer: writer.close(), "127.0.0.1", 0, ssl=context)
    port = server.sockets[0].getsockname()[1]
    assert not await store_mailer(smtp_settings("localhost", port, "ssl/tls"), ["localhost"]).check_ping()
    server.close()
    assert server_names == ["localhost"]
