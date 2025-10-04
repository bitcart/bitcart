from __future__ import annotations

import asyncio
import signal
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from decimal import Decimal
from queue import Queue
from typing import TYPE_CHECKING, Any, cast

import pytest
from aiohttp import web
from bitcart import BTC  # type: ignore
from bitcart.utils import bitcoins
from httpx_ws import AsyncWebSocketSession, aconnect_ws

from api.constants import MAX_CONFIRMATION_WATCH
from api.ext.moneyformat import truncate
from api.settings import Settings
from tests.functional import utils
from tests.helper import create_store, create_wallet

if TYPE_CHECKING:
    from httpx import AsyncClient as TestClient

REGTEST_XPUB = "dutch field mango comfort symptom smooth wide senior tongue oyster wash spoon"
REGTEST_XPUB2 = "hungry ordinary similar more spread math general wire jealous valve exhaust emotion"
LIGHTNING_CHANNEL_AMOUNT = bitcoins(200_000)
LNPAY_AMOUNT = LIGHTNING_CHANNEL_AMOUNT / 10
LIGHTNING_INVOICE_AMOUNT = str(LNPAY_AMOUNT / 2)
PAYOUTS_FUND_AMOUNT = Decimal("1.0")

settings = Settings()
MAIN_PORT = settings.config("BTC_PORT", cast=int, default=5000)
MAIN_URL = f"http://localhost:{MAIN_PORT}"
del settings

INVOICE_AMOUNT = "0.00018"  # as of 2 Apr 2023, we do this to avoid calling coingecko

pytestmark = pytest.mark.anyio


@pytest.fixture
def worker() -> Iterator[None]:
    process = utils.start_worker()
    yield
    process.send_signal(signal.SIGINT)
    process.wait()


async def get_status(client: TestClient, obj_id: str, token: str) -> str:
    resp1 = await client.get(f"/invoices/{obj_id}")
    resp2 = await client.get(f"/payouts/{obj_id}", headers={"Authorization": f"Bearer {token}"})
    resp = resp1 if resp1.status_code == 200 else resp2
    assert resp.status_code == 200
    return resp.json()["status"]


async def check_invoice_status(
    action_func: Callable[[], Awaitable[Any]],
    client: TestClient,
    invoice_id: str,
    expected_status: str,
    allow_next: bool = False,
    exception_status: str | None = None,
    sent_amount: Decimal | None = None,
) -> None:
    async with asyncio.timeout(30):
        ws: AsyncWebSocketSession
        async with aconnect_ws(f"/ws/invoices/{invoice_id}", client) as ws:
            await action_func()
            ws = cast(AsyncWebSocketSession, ws)
            msg = await ws.receive_json()
            if allow_next:  # when there are two statuses in a row (zeroconf)
                msg = await ws.receive_json()
            assert msg["status"] == expected_status
            if exception_status is not None:
                assert msg["exception_status"] == exception_status
            if sent_amount is not None:
                assert Decimal(msg["sent_amount"]) == Decimal(sent_amount)
    await asyncio.sleep(1)  # ensure IPNs are already sent


async def wait_for_balance(address: str, expected_balance: Decimal) -> None:
    wallet = BTC(xpub=address, rpc_url=MAIN_URL)
    while True:
        balance = await wallet.balance()
        balance = balance["confirmed"] + balance["unconfirmed"]
        await asyncio.sleep(1)
        if balance >= expected_balance:
            break
    await asyncio.sleep(3)


async def wait_for_local_tx(wallet: BTC, tx_hash: str) -> None:
    async with asyncio.timeout(30):
        while True:
            try:
                confirmations = (await wallet.server.get_tx_status(tx_hash))["confirmations"]
                if confirmations >= 1:
                    break
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)
    await asyncio.sleep(3)


async def send_to_address(address: str, amount: Decimal, confirm: bool = False, wait_balance: bool = False) -> str:
    tx_hash = utils.run_shell(["sendtoaddress", address, str(amount)])
    if confirm:
        utils.run_shell(["newblocks", "1"])
    if wait_balance:
        await wait_for_balance(address, Decimal(amount))
    return tx_hash


def find_channel(channels: list[dict[str, Any]], channel_point: str) -> dict[str, Any]:
    for channel in channels:
        if channel["channel_point"] == channel_point:
            return channel
    raise ValueError(f"Channel {channel_point} not found")


async def wait_for_channel_opening(regtest_wallet: BTC, channel_point: str) -> None:
    while True:
        channels = await regtest_wallet.list_channels()
        channel = find_channel(channels, channel_point)
        await asyncio.sleep(1)
        if channel["state"] == "OPEN":
            break
    await asyncio.sleep(1)


@pytest.fixture
async def regtest_wallet() -> BTC:
    return BTC(xpub=REGTEST_XPUB, rpc_url=MAIN_URL)


@pytest.fixture
async def regtest_lnnode() -> BTC:
    return BTC(xpub=REGTEST_XPUB2, rpc_url="http://localhost:5110")


@pytest.fixture
async def prepare_ln_channels(regtest_wallet: BTC, regtest_lnnode: BTC) -> AsyncIterator[None]:
    node_id = await regtest_lnnode.node_id
    # first fund the channel opener
    fund_amount = 10 * LIGHTNING_CHANNEL_AMOUNT
    address = (await regtest_wallet.add_request(fund_amount))["address"]
    await send_to_address(address, fund_amount, confirm=True, wait_balance=True)
    channel_point = await regtest_wallet.open_channel(node_id, LIGHTNING_CHANNEL_AMOUNT)
    # make it fully open
    utils.run_shell(["newblocks", "3"])
    await wait_for_channel_opening(regtest_wallet, channel_point)
    # transfer some amount to the other node to be able to receive
    invoice = (await regtest_lnnode.add_invoice(LNPAY_AMOUNT))["lightning_invoice"]
    lnpay_result = await regtest_wallet.lnpay(invoice)
    assert lnpay_result["success"], lnpay_result
    yield
    await regtest_wallet.close_channel(channel_point)


type MPQueue = Queue[tuple[dict[str, Any], str]]


@pytest.fixture
def queue() -> MPQueue:
    return Queue()


@pytest.fixture
async def ipn_server(queue: MPQueue, client: TestClient, token: str) -> AsyncIterator[str]:
    host = "0.0.0.0"
    port = 8080

    async def handle_post(request: web.Request) -> web.Response:
        data = await request.json()
        # to ensure status during IPN matches the one sent
        status = await get_status(client, data["id"], token=token)
        queue.put((data, status))
        return web.json_response({})

    app = web.Application()
    app.router.add_post("/", handle_post)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    yield f"http://{host}:{port}"
    await runner.cleanup()


def check_status(queue: MPQueue, data: dict[str, Any]) -> None:
    queue_data = queue.get()
    assert queue_data[0] == data
    assert queue_data[0]["status"] == queue_data[1]


@pytest.fixture
async def regtest_api_wallet(client: TestClient, token: str, anyio_backend: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return await create_wallet(client, token, xpub=REGTEST_XPUB)


@pytest.fixture
async def regtest_api_store(
    client: TestClient,
    token: str,
    regtest_api_wallet: dict[str, Any],
    anyio_backend: tuple[str, dict[str, Any]],
) -> dict[str, Any]:
    return await create_store(client, token, custom_store_attrs={"wallets": [regtest_api_wallet["id"]]})


@pytest.mark.parametrize("speed", range(MAX_CONFIRMATION_WATCH + 1))
async def test_onchain_pay_flow(
    client: TestClient,
    regtest_api_store: dict[str, Any],
    token: str,
    worker: None,
    queue: MPQueue,
    ipn_server: str,
    speed: int,
) -> None:
    store_id = regtest_api_store["id"]
    resp = await client.patch(
        f"/stores/{store_id}/checkout_settings",
        json={"transaction_speed": speed},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["checkout_settings"]["transaction_speed"] == speed
    invoice = (
        await client.post(
            "/invoices",
            json={"price": INVOICE_AMOUNT, "currency": "BTC", "store_id": store_id, "notification_url": ipn_server},
        )
    ).json()
    assert invoice["status"] == "pending"
    pay_details = invoice["payments"][0]
    address = pay_details["payment_address"]
    amount = pay_details["amount"]
    invoice_id = invoice["id"]
    zeroconf = speed == 0
    expected_status = "complete" if zeroconf else "paid"
    await check_invoice_status(
        lambda: send_to_address(address, amount),
        client,
        invoice_id,
        expected_status,
        sent_amount=amount,
        exception_status="none",
        allow_next=zeroconf,
    )


async def test_exception_statuses(
    client: TestClient,
    regtest_api_store: dict[str, Any],
    token: str,
    worker: None,
    ipn_server: str,
) -> None:
    store_id = regtest_api_store["id"]
    invoice = (await client.post("/invoices", json={"price": INVOICE_AMOUNT, "currency": "BTC", "store_id": store_id})).json()
    pay_details = invoice["payments"][0]
    address = pay_details["payment_address"]
    amount = Decimal(pay_details["amount"])
    part1 = truncate(amount / 2, 8)
    part2 = amount - part1
    await asyncio.sleep(3)  # wait for the worker startup (remove when electrum fixes pending tx_hashes returning)
    invoice_id = invoice["id"]
    await check_invoice_status(
        lambda: send_to_address(address, part1),
        client,
        invoice_id,
        "pending",
        exception_status="paid_partial",
        sent_amount=part1,
    )
    await check_invoice_status(
        lambda: send_to_address(address, part2),
        client,
        invoice_id,
        "complete",
        exception_status="none",
        sent_amount=pay_details["amount"],
        allow_next=True,
    )


async def test_lightning_pay_flow(
    client: TestClient,
    regtest_api_wallet: dict[str, Any],
    regtest_api_store: dict[str, Any],
    token: str,
    worker: None,
    queue: MPQueue,
    ipn_server: str,
    prepare_ln_channels: None,
    regtest_lnnode: BTC,
) -> None:
    wallet_id = regtest_api_wallet["id"]
    store_id = regtest_api_store["id"]
    resp = await client.patch(
        f"/wallets/{wallet_id}",
        json={"lightning_enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["lightning_enabled"]
    invoice = (
        await client.post(
            "/invoices",
            json={"price": LIGHTNING_INVOICE_AMOUNT, "currency": "BTC", "store_id": store_id, "notification_url": ipn_server},
        )
    ).json()
    assert invoice["status"] == "pending"
    pay_details = invoice["payments"][1]  # lightning methods are always created after onchain ones

    async def pay_invoice() -> None:
        lnpay_result = await regtest_lnnode.lnpay(pay_details["payment_address"])
        assert lnpay_result["success"], lnpay_result

    invoice_id = invoice["id"]
    await check_invoice_status(
        pay_invoice, client, invoice_id, "complete", exception_status="none", sent_amount=pay_details["amount"]
    )
    assert queue.qsize() == 1
    check_status(queue, {"id": invoice["id"], "status": "complete"})
    # check that it was paid with lightning actually
    resp = await client.get(f"/invoices/{invoice_id}")
    assert resp.json()["paid_currency"] == "BTC (⚡)"
    assert resp.json()["payment_id"] == pay_details["id"]


async def apply_batch_payout_action(
    client: TestClient, token: str, command: str, ids: list[str], options: dict[str, Any] | None = None
) -> None:
    if options is None:
        options = {}
    resp = await client.post(
        "/payouts/batch",
        json={"command": command, "ids": ids, "options": options},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() is True


async def check_payout_status(client: TestClient, token: str, obj_id: str, expected_status: str) -> None:
    resp = await client.get(f"/payouts/{obj_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == expected_status


async def test_payouts(
    client: TestClient,
    regtest_wallet: BTC,
    regtest_api_wallet: dict[str, Any],
    regtest_api_store: dict[str, Any],
    token: str,
    worker: None,
    queue: MPQueue,
    ipn_server: str,
) -> None:
    wallet_id = regtest_api_wallet["id"]
    store_id = regtest_api_store["id"]
    address = (await regtest_wallet.add_request())["address"]
    await send_to_address(address, PAYOUTS_FUND_AMOUNT, confirm=True, wait_balance=True)
    payout = (
        await client.post(
            "/payouts",
            json={
                "destination": address,
                "amount": 5,
                "store_id": store_id,
                "wallet_id": wallet_id,
                "notification_url": ipn_server,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    assert payout["status"] == "pending"
    # test batch actions first, note that we don't restrict user much
    await apply_batch_payout_action(client, token, "approve", [payout["id"]])
    await check_payout_status(client, token, payout["id"], "approved")
    await apply_batch_payout_action(client, token, "cancel", [payout["id"]])
    await check_payout_status(client, token, payout["id"], "cancelled")
    await apply_batch_payout_action(client, token, "approve", [payout["id"]])
    # but approve works on pending statuses only
    await check_payout_status(client, token, payout["id"], "cancelled")
    # Execute the actual payout
    await apply_batch_payout_action(client, token, "send", [payout["id"]])
    payout = (await client.get(f"/payouts/{payout['id']}", headers={"Authorization": f"Bearer {token}"})).json()
    assert payout["status"] == "sent"
    assert payout["tx_hash"] is not None
    tx_data = await regtest_wallet.get_tx(payout["tx_hash"])
    assert tx_data["confirmations"] == 0
    utils.run_shell(["newblocks", "1"])
    await wait_for_local_tx(regtest_wallet, payout["tx_hash"])
    payout = (await client.get(f"/payouts/{payout['id']}", headers={"Authorization": f"Bearer {token}"})).json()
    assert payout["status"] == "complete"
    assert payout["used_fee"] > 0
    tx_data = await regtest_wallet.get_tx(payout["tx_hash"])
    assert tx_data["confirmations"] == 1
    # Now it's immutable
    old_tx_hash = payout["tx_hash"]
    await apply_batch_payout_action(client, token, "send", [payout["id"]])
    payout = (await client.get(f"/payouts/{payout['id']}", headers={"Authorization": f"Bearer {token}"})).json()
    assert payout["tx_hash"] == old_tx_hash
    # Check that IPN worked too
    assert queue.qsize() == 2
    check_status(queue, {"id": payout["id"], "status": "sent"})
    check_status(queue, {"id": payout["id"], "status": "complete"})
    # Check signing on watch-only wallet
    xpub = await regtest_wallet.server.getmpk()
    watchonly_wallet = await create_wallet(client, token, xpub=xpub)
    payout = (
        await client.post(
            "/payouts",
            json={"destination": address, "amount": 5, "store_id": store_id, "wallet_id": watchonly_wallet["id"]},
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    await apply_batch_payout_action(client, token, "send", [payout["id"]])
    await check_payout_status(client, token, payout["id"], "failed")  # no private key available
    # now try sending key
    await apply_batch_payout_action(
        client, token, "send", [payout["id"]], options={"wallets": {watchonly_wallet["id"]: REGTEST_XPUB}}
    )
    await check_payout_status(client, token, payout["id"], "sent")
    # test max fee
    payout = (
        await client.post(
            "/payouts",
            json={
                "destination": address,
                "amount": "0.1",
                "store_id": store_id,
                "wallet_id": wallet_id,
                "max_fee": str(bitcoins(1)),
                "currency": "BTC",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    ).json()
    await apply_batch_payout_action(client, token, "send", [payout["id"]])
    await check_payout_status(client, token, payout["id"], "pending")  # when fee exceeds the limit, we don't change status
