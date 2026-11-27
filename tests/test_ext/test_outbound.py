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
from outbound_guard import OutboundDenied

from api import utils
from api.ext.ssh import create_ssh_client
from api.schemas.configurator import ConfiguratorSSHSettings
from api.schemas.misc import EmailSettings
from api.services.email import EmailService, ServerEmailService
from api.services.ipn_sender import IPNSender
from api.services.outbound import OutboundService
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from tests.helper import allow_outbound, create_store, create_token, create_user, set_allowed_hosts

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient as TestClient

pytestmark = pytest.mark.anyio


async def get_policies(client: TestClient, token: str) -> dict[str, Any]:
    return (await client.get("/manage/policies", headers={"Authorization": f"Bearer {token}"})).json()


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
    client: TestClient, token: str, start_server: ServerFactory, smtp_server: FakeSMTPServer, outbound: OutboundService
) -> None:
    server, port = await start_server()
    url = f"http://127.0.0.1:{port}/"
    email_service = EmailService(outbound)
    async with outbound.session() as session:
        for _ in range(2):
            with pytest.raises(aiohttp.ClientOSError):
                await session.get(url)
            assert not await email_service.check_ping(smtp_settings("localhost", smtp_server.port))
            await set_allowed_hosts(client, token, [f"127.0.0.1:{port}", f"localhost:{smtp_server.port}"])
            async with session.get(url, headers={"Connection": "close"}) as response:
                assert response.status == 200
            assert await email_service.check_ping(smtp_settings("localhost", smtp_server.port))
            await set_allowed_hosts(client, token, [])
    assert len(server.requests) == 2


async def test_only_the_service_uses_allowed_hosts(
    client: TestClient, token: str, start_server: ServerFactory, outbound: OutboundService, mocker: pytest_mock.MockerFixture
) -> None:
    read = mocker.spy(SettingService, "get_stored_setting")
    server, port = await start_server()
    await set_allowed_hosts(client, token, ["127.0.0.1", "localhost"])
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
    explorer = AsyncMock(return_value="")
    plugin_registry.register_filter("get_coin_explorer", explorer)
    assert await outbound.get_allowed_hosts() == ["n8n:5678"]
    explorer.assert_not_called()


async def test_server_email_does_not_need_allowed_hosts(client: TestClient, token: str, smtp_server: FakeSMTPServer) -> None:
    email_settings = smtp_settings("localhost", smtp_server.port).model_dump()
    headers = {"Authorization": f"Bearer {token}"}
    store = await create_store(client, token, {"email_settings": email_settings})
    assert (await client.get(f"/stores/{store['id']}/ping", headers=headers)).json() is False
    assert smtp_server.commands == []
    await client.post("/manage/policies", json={"email_settings": email_settings}, headers=headers)
    assert (await client.get("/manage/testping", headers=headers)).json() is True
    assert (await client.get(f"/stores/{store['id']}/ping", headers=headers)).json() is False


async def test_server_email_times_out(mocker: pytest_mock.MockerFixture, outbound: OutboundService) -> None:
    mocker.patch("api.services.email.SMTP_TIMEOUT", 0.05)
    mocker.patch("api.services.email.socket.create_connection", lambda *_: time.sleep(0.5))
    started = time.monotonic()
    assert not await ServerEmailService(outbound).check_ping(smtp_settings("smtp.example.com", 25))
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


async def test_denials_of_the_service_name_the_policy(
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


async def test_smtp_connects_only_to_checked_addresses(
    smtp_server: FakeSMTPServer, outbound: OutboundService, client: TestClient, token: str
) -> None:
    email_service = EmailService(outbound)
    for host in ("127.0.0.1", "localhost", "127.1", "2130706433", "::1"):
        assert not await email_service.check_ping(smtp_settings(host, smtp_server.port))
    assert smtp_server.commands == []
    await set_allowed_hosts(client, token, [f"localhost:{smtp_server.port}"])
    assert await email_service.check_ping(smtp_settings("localhost", smtp_server.port))
    assert "VRFY" in smtp_server.commands


async def test_smtp_keeps_the_hostname_for_tls(outbound: OutboundService, client: TestClient, token: str) -> None:
    server_names: list[str | None] = []
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.sni_callback = lambda _, name, __: server_names.append(name)
    server = await asyncio.start_server(lambda _, writer: writer.close(), "127.0.0.1", 0, ssl=context)
    port = server.sockets[0].getsockname()[1]
    await set_allowed_hosts(client, token, ["localhost"])
    assert not await EmailService(outbound).check_ping(smtp_settings("localhost", port, "ssl/tls"))
    server.close()
    assert server_names == ["localhost"]
