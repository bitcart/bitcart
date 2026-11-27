from __future__ import annotations

import asyncio
import socket
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest
import pytest_mock
from bitcart import BTC  # type: ignore[attr-defined]
from bitcart.errors import BaseError as BitcartBaseError

from tests.helper import allow_outbound, create_token, create_wallet

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient
    from httpx import Response

pytestmark = pytest.mark.anyio

PUBKEY = "02" + "ab" * 32
PUBLIC_IP = "93.184.215.14"
PUBLIC_IPV6 = "2606:4700::1111"
ONION = "a2" * 28 + ".onion"
CHANNEL_POINT = "00" * 32 + ":0"
DNS = {
    "peer.example.com": [PUBLIC_IP],
    "peer.example.com.": [PUBLIC_IP],
    "mixed.example.com": ["10.0.0.5", PUBLIC_IP],
    "ipv6.example.com": [PUBLIC_IPV6],
    "internal.example.com": ["10.0.0.5"],
    "redis": ["172.18.0.2"],
    "metadata.internal": ["169.254.169.254"],
    "lnd": ["10.0.0.7"],
    "nonexistent.invalid": [],
    "short.onion": [],
    f"sub.{ONION}": [],
    f"{ONION}.": [],
}

type Dns = Callable[[dict[str, list[str]]], list[str]]


@pytest.fixture
def fake_dns(mocker: pytest_mock.MockerFixture) -> Dns:
    def use(answers: dict[str, list[str]]) -> list[str]:
        loop = asyncio.get_running_loop()
        real_getaddrinfo = loop.getaddrinfo
        lookups: list[str] = []

        async def getaddrinfo(host: str, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
            if host not in answers:
                return await real_getaddrinfo(host, port, *args, **kwargs)
            lookups.append(host)
            if not answers[host]:
                raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
            return [
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, port, 0, 0))
                if ":" in address
                else (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
                for address in answers[host]
            ]

        mocker.patch.object(loop, "getaddrinfo", getaddrinfo)
        return lookups

    return use


@pytest.fixture
def open_channel(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return mocker.patch.object(BTC, "open_channel", AsyncMock(return_value=CHANNEL_POINT))


@pytest.fixture
def uses_gossip(mocker: pytest_mock.MockerFixture) -> AsyncMock:
    return mocker.patch("api.ext.lightning.uses_gossip", return_value=False)


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
        (f"{PUBKEY}@{PUBLIC_IP}:9736", f"{PUBKEY}@{PUBLIC_IP}:9736"),
        (f"{PUBKEY}@{PUBLIC_IP}", f"{PUBKEY}@{PUBLIC_IP}:9735"),
        (f"{PUBKEY.upper()}@peer.example.com:9735", f"{PUBKEY}@{PUBLIC_IP}:9735"),
        (f"{PUBKEY}@peer.example.com", f"{PUBKEY}@{PUBLIC_IP}:9735"),
        (f"{PUBKEY}@peer.example.com.:1", f"{PUBKEY}@{PUBLIC_IP}:1"),
        (f"{PUBKEY}@mixed.example.com", f"{PUBKEY}@{PUBLIC_IP}:9735"),
        (f"{PUBKEY}@[{PUBLIC_IPV6}]:65535", f"{PUBKEY}@[{PUBLIC_IPV6}]:65535"),
        (f"{PUBKEY}@[{PUBLIC_IPV6}]", f"{PUBKEY}@[{PUBLIC_IPV6}]:9735"),
        (f"{PUBKEY}@[2606:4700:0::1111]", f"{PUBKEY}@[{PUBLIC_IPV6}]:9735"),
        (f"{PUBKEY}@ipv6.example.com", f"{PUBKEY}@[{PUBLIC_IPV6}]:9735"),
        (f"{PUBKEY}@{ONION}:9735", f"{PUBKEY}@{ONION}:9735"),
        (f"{PUBKEY}@{ONION.upper()}", f"{PUBKEY}@{ONION}:9735"),
        (PUBKEY, PUBKEY),
    ],
)
async def test_public_peers_are_dialled_by_the_checked_address(
    connection_string: str,
    dialled: str,
    client: TestClient,
    limited_wallet: tuple[str, str],
    open_channel: AsyncMock,
    uses_gossip: AsyncMock,
    fake_dns: Dns,
) -> None:
    fake_dns(DNS)
    resp = await open_with(client, limited_wallet, connection_string)
    assert (resp.status_code, resp.json()) == (200, CHANNEL_POINT)
    assert open_channel.call_args.args[0] == dialled


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "127.0.0.1:6379",
        "localhost:6379",
        "0.0.0.0:9735",
        "127.1:6379",
        "2130706433:6379",
        "0x7f000001:6379",
        "10.0.0.5",
        "100.64.0.1",
        "169.254.169.254:80",
        "redis:6379",
        "metadata.internal:80",
        "internal.example.com",
        "lnd",
        "[::1]:6379",
        "[::]",
        "[::ffff:127.0.0.1]:6379",
        "[::ffff:7f00:1]:6379",
        "[64:ff9b::7f00:1]:6379",
        "[fd00::5]",
        "nonexistent.invalid",
    ],
)
async def test_other_peers_are_refused(
    address: str,
    client: TestClient,
    limited_wallet: tuple[str, str],
    open_channel: AsyncMock,
    uses_gossip: AsyncMock,
    fake_dns: Dns,
) -> None:
    fake_dns(DNS)
    check_refused(await open_with(client, limited_wallet, f"{PUBKEY}@{address}"))
    open_channel.assert_not_called()


@pytest.mark.parametrize(
    "connection_string",
    [
        "",
        "test",
        "@",
        f"@{PUBLIC_IP}:9735",
        f"{PUBKEY}@",
        f"{PUBKEY}@@{PUBLIC_IP}",
        f"{PUBKEY}@user@{PUBLIC_IP}:9735",
        f"{PUBKEY}@{PUBLIC_IP}@127.0.0.1:6379",
        f"{PUBKEY}@user:password@{PUBLIC_IP}:9735",
        f"{PUBKEY}@{PUBLIC_IP}:",
        f"{PUBKEY}@{PUBLIC_IP}:0",
        f"{PUBKEY}@{PUBLIC_IP}:65536",
        f"{PUBKEY}@{PUBLIC_IP}:+1",
        f"{PUBKEY}@{PUBLIC_IP}:１２",
        f"{PUBKEY}@{PUBLIC_IP}:1:2",
        f"{PUBKEY}@{PUBLIC_IP}:9735/path",
        f"{PUBKEY}@{PUBLIC_IP}\n:9735",
        f"{PUBKEY}@{PUBLIC_IP} :9735",
        f"{PUBKEY}@peer.example.com\x00:9735",
        f"{PUBKEY}@{PUBLIC_IPV6}",
        f"{PUBKEY}@[{PUBLIC_IPV6}",
        f"{PUBKEY}@[{PUBLIC_IPV6}]9735",
        f"{PUBKEY}@[{PUBLIC_IPV6}%eth0]:9735",
        f"{PUBKEY}@[{PUBLIC_IP}]:9735",
        f"{PUBKEY}@[peer.example.com]:9735",
        f"{PUBKEY}@{'a' * 64}.example.com",
        f"{PUBKEY}@..:9735",
        f"{PUBKEY}@short.onion",
        f"{PUBKEY}@sub.{ONION}",
        f"{PUBKEY}@{ONION}.:9735",
        f"{PUBKEY[:-1]}@{PUBLIC_IP}",
        f"{PUBKEY}0@{PUBLIC_IP}",
        f"{PUBKEY[:-2]} ab@{PUBLIC_IP}",
        f"{PUBKEY[:-2]}zz@{PUBLIC_IP}",
        f"{PUBKEY[:-2]}zz",
        f"{PUBKEY}:9735",
        f"{PUBKEY} {PUBKEY}",
    ],
)
async def test_unparseable_input_is_refused(
    connection_string: str,
    client: TestClient,
    limited_wallet: tuple[str, str],
    open_channel: AsyncMock,
    uses_gossip: AsyncMock,
    fake_dns: Dns,
) -> None:
    fake_dns(DNS)
    check_refused(await open_with(client, limited_wallet, connection_string))
    open_channel.assert_not_called()


async def test_denied_and_failed_opens_look_the_same(
    client: TestClient, limited_wallet: tuple[str, str], open_channel: AsyncMock
) -> None:
    denied = await open_with(client, limited_wallet, f"{PUBKEY}@127.0.0.1:6379")
    open_channel.assert_not_called()
    open_channel.side_effect = BitcartBaseError("Connection refused by peer")
    failed = await open_with(client, limited_wallet, f"{PUBKEY}@{PUBLIC_IP}:9735")
    open_channel.assert_called_once()
    assert (denied.status_code, denied.content) == (failed.status_code, failed.content)
    check_refused(denied)


async def test_second_lookup_cannot_change_the_address(
    client: TestClient, limited_wallet: tuple[str, str], open_channel: AsyncMock, fake_dns: Dns
) -> None:
    answers = {"rebind.example.com": [PUBLIC_IP]}
    lookups = fake_dns(answers)

    async def resolve_again(node_id: str, *args: Any, **kwargs: Any) -> str:
        answers["rebind.example.com"] = ["127.0.0.1"]
        host = node_id.partition("@")[2].rpartition(":")[0]
        assert socket.getaddrinfo(host, 9735)[0][4][0] == PUBLIC_IP
        return CHANNEL_POINT

    open_channel.side_effect = resolve_again
    assert (await open_with(client, limited_wallet, f"{PUBKEY}@rebind.example.com:9735")).status_code == 200
    assert lookups == ["rebind.example.com"]
    check_refused(await open_with(client, limited_wallet, f"{PUBKEY}@rebind.example.com:9735"))
    open_channel.assert_called_once()


async def test_allowed_peers_can_be_internal(
    client: TestClient,
    limited_wallet: tuple[str, str],
    open_channel: AsyncMock,
    fake_dns: Dns,
    mocker: pytest_mock.MockerFixture,
) -> None:
    fake_dns(DNS)
    allow_outbound(mocker, "lnd:9735", "10.0.0.5")
    for address, dialled in (("lnd", "10.0.0.7:9735"), ("internal.example.com:1", "10.0.0.5:1")):
        assert (await open_with(client, limited_wallet, f"{PUBKEY}@{address}")).status_code == 200
        assert open_channel.call_args.args[0] == f"{PUBKEY}@{dialled}"
    open_channel.reset_mock()
    check_refused(await open_with(client, limited_wallet, f"{PUBKEY}@lnd:6379"))
    open_channel.assert_not_called()


async def test_bare_pubkey_depends_on_gossip(
    client: TestClient, limited_wallet: tuple[str, str], open_channel: AsyncMock, uses_gossip: AsyncMock
) -> None:
    uses_gossip.return_value = True
    check_refused(await open_with(client, limited_wallet, PUBKEY))
    uses_gossip.side_effect = BitcartBaseError("Unknown method")
    check_refused(await open_with(client, limited_wallet, PUBKEY))
    open_channel.assert_not_called()
    assert (await open_with(client, limited_wallet, f"{PUBKEY}@{PUBLIC_IP}")).status_code == 200


async def test_gossip_state_is_read_from_the_daemon(
    client: TestClient, limited_wallet: tuple[str, str], open_channel: AsyncMock, mocker: pytest_mock.MockerFixture
) -> None:
    assert (await open_with(client, limited_wallet, PUBKEY)).status_code == 200
    assert open_channel.call_args.args[0] == PUBKEY
    open_channel.reset_mock()
    for value in (None, True, "false"):
        coin = mocker.Mock(open_channel=open_channel, server=mocker.Mock(getconfig=AsyncMock(return_value=value)))
        mocker.patch("api.services.crud.wallets.WalletService.get_wallet_coin_by_id", return_value=coin)
        check_refused(await open_with(client, limited_wallet, PUBKEY))
    open_channel.assert_not_called()
