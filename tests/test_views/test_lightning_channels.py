from __future__ import annotations

import asyncio
import socket
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest
import pytest_mock
from bitcart import BTC  # type: ignore[attr-defined]
from bitcart.errors import BaseError as BitcartBaseError

from tests.helper import create_token, create_wallet, set_allowed_hosts

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient
    from httpx import Response

pytestmark = pytest.mark.anyio

PUBKEY = "02" + "ab" * 32
PUBLIC_IP = "93.184.215.14"
PUBLIC_IPV6 = "2606:4700::1111"
ONION = "a2" * 28 + ".onion"
CHANNEL_POINT = "00" * 32 + ":0"
DNS = {"peer.example.com": PUBLIC_IP, "ipv6.example.com": PUBLIC_IPV6, "lnd": "10.0.0.7"}


@pytest.fixture(autouse=True)
async def fake_dns(mocker: pytest_mock.MockerFixture) -> None:
    loop = asyncio.get_running_loop()
    real_getaddrinfo = loop.getaddrinfo

    async def getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        if host not in DNS:
            return await real_getaddrinfo(host, port, *args, **kwargs)
        address = DNS[host]
        if ":" in address:
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port, 0, 0))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    mocker.patch.object(loop, "getaddrinfo", getaddrinfo)


@pytest.fixture
def open_channel(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return mocker.patch.object(BTC, "open_channel", AsyncMock(return_value=CHANNEL_POINT))


@pytest.fixture
async def limited_wallet(client: TestClient, limited_user: dict[str, Any]) -> tuple[str, str]:
    token = (await create_token(client, limited_user, permissions=["full_control"]))["access_token"]
    return (await create_wallet(client, token))["id"], token


async def open_with(client: TestClient, limited_wallet: tuple[str, str], node_id: str) -> Response:
    wallet_id, token = limited_wallet
    return await client.post(
        f"/wallets/{wallet_id}/channels/open",
        json={"node_id": node_id, "amount": 0.1},
        headers={"Authorization": f"Bearer {token}"},
    )


def check_refused(resp: Response) -> None:
    assert (resp.status_code, resp.json()) == (400, {"detail": "Failed to open channel"})


@pytest.mark.parametrize(
    "connection_string,dialled",
    [
        (f"{PUBKEY.upper()}@peer.example.com", f"{PUBKEY}@{PUBLIC_IP}:9735"),
        (f"{PUBKEY}@ipv6.example.com:9736", f"{PUBKEY}@[{PUBLIC_IPV6}]:9736"),
        (f"{PUBKEY}@{ONION}", f"{PUBKEY}@{ONION}:9735"),
    ],
)
async def test_peers_are_dialled_by_the_checked_address(
    connection_string: str,
    dialled: str,
    client: TestClient,
    limited_wallet: tuple[str, str],
    open_channel: AsyncMock,
) -> None:
    resp = await open_with(client, limited_wallet, connection_string)
    assert (resp.status_code, resp.json()) == (200, CHANNEL_POINT)
    assert open_channel.call_args.args[0] == dialled


@pytest.mark.parametrize(
    "connection_string",
    [
        "test",
        f"{PUBKEY}@user@{PUBLIC_IP}",
        f"{PUBKEY}@{PUBLIC_IPV6}",
        f"{PUBKEY}@[{PUBLIC_IP}]",
        f"{PUBKEY}@{PUBLIC_IP}:65536",
        f"{PUBKEY}@lnd",
    ],
)
async def test_invalid_and_internal_peers_are_refused(
    connection_string: str, client: TestClient, limited_wallet: tuple[str, str], open_channel: AsyncMock
) -> None:
    check_refused(await open_with(client, limited_wallet, connection_string))
    open_channel.assert_not_called()


async def test_internal_peers_need_the_owner_allowed_hosts(
    client: TestClient,
    token: str,
    limited_user: dict[str, Any],
    limited_wallet: tuple[str, str],
    open_channel: AsyncMock,
) -> None:
    await set_allowed_hosts(client, token, ["lnd"])
    check_refused(await open_with(client, limited_wallet, f"{PUBKEY}@lnd"))
    await set_allowed_hosts(client, token, [])
    resp = await client.patch(
        f"/users/{limited_user['id']}",
        json={"allowed_internal_hosts": ["lnd:9735"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert (await open_with(client, limited_wallet, f"{PUBKEY}@lnd")).status_code == 200
    assert open_channel.call_args.args[0] == f"{PUBKEY}@10.0.0.7:9735"
    check_refused(await open_with(client, limited_wallet, f"{PUBKEY}@lnd:6379"))
    open_channel.assert_called_once()


async def test_denied_and_failed_opens_look_the_same(
    client: TestClient, limited_wallet: tuple[str, str], open_channel: AsyncMock
) -> None:
    denied = await open_with(client, limited_wallet, f"{PUBKEY}@127.0.0.1:6379")
    open_channel.side_effect = BitcartBaseError("Connection refused by peer")
    failed = await open_with(client, limited_wallet, f"{PUBKEY}@{PUBLIC_IP}:9735")
    open_channel.assert_called_once()
    assert (denied.status_code, denied.content) == (failed.status_code, failed.content)
    check_refused(denied)


@pytest.mark.parametrize(
    "use_gossip,allowed", [(False, True), (True, False), (None, False), ("false", False), (BitcartBaseError("No"), False)]
)
async def test_bare_pubkey_is_allowed_only_without_gossip(
    use_gossip: Any,
    allowed: bool,
    client: TestClient,
    limited_wallet: tuple[str, str],
    open_channel: AsyncMock,
    mocker: pytest_mock.MockerFixture,
) -> None:
    coin = mocker.Mock(open_channel=open_channel, server=mocker.Mock(getconfig=AsyncMock(side_effect=[use_gossip])))
    mocker.patch("api.services.crud.wallets.WalletService.get_wallet_coin_by_id", return_value=coin)
    resp = await open_with(client, limited_wallet, PUBKEY)
    if allowed:
        assert resp.status_code == 200
        assert open_channel.call_args.args[0] == PUBKEY
    else:
        check_refused(resp)
        open_channel.assert_not_called()
