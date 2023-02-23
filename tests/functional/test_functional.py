import asyncio
import multiprocessing
import signal
from decimal import Decimal

import async_timeout
import pytest
from aiohttp import web
from bitcart import BTC
from bitcart.utils import bitcoins

from api.constants import MAX_CONFIRMATION_WATCH
from api.ext.moneyformat import truncate
from tests.functional import utils
from tests.helper import create_store, create_wallet

REGTEST_XPUB = "dutch field mango comfort symptom smooth wide senior tongue oyster wash spoon"
REGTEST_XPUB2 = "hungry ordinary similar more spread math general wire jealous valve exhaust emotion"
LIGHTNING_CHANNEL_AMOUNT = Decimal("0.1")
LNPAY_AMOUNT = LIGHTNING_CHANNEL_AMOUNT / 10

pytestmark = pytest.mark.anyio


@pytest.fixture
def worker():
    process = utils.start_worker()
    yield
    process.send_signal(signal.SIGINT)
    process.wait()


async def get_status(client, obj_id, token):
    resp1 = await client.get(f"/invoices/{obj_id}")
    resp2 = await client.get(f"/payouts/{obj_id}", headers={"Authorization": f"Bearer {token}"})
    resp = resp1 if resp1.status_code == 200 else resp2
    assert resp.status_code == 200
    return resp.json()["status"]


async def check_invoice_status(
    ws_client, invoice_id, expected_status, allow_next=False, exception_status=None, sent_amount=None
):
    async with async_timeout.timeout(30):
        async with ws_client.websocket_connect(f"/ws/invoices/{invoice_id}") as ws:
            msg = await ws.receive_json()
            if allow_next:  # when there are two statuses in a row (zeroconf)
                msg = await ws.receive_json()
            assert msg["status"] == expected_status
            if exception_status is not None:
                assert msg["exception_status"] == exception_status
            if sent_amount is not None:
                assert Decimal(msg["sent_amount"]) == Decimal(sent_amount)
    await asyncio.sleep(1)  # ensure IPNs are already sent


async def wait_for_balance(address, expected_balance):
    wallet = BTC(xpub=address)
    while True:
        balance = await wallet.balance()
        balance = balance["confirmed"] + balance["unconfirmed"]
        await asyncio.sleep(1)
        if balance >= expected_balance:
            break
    await asyncio.sleep(3)


async def wait_for_local_tx(wallet, tx_hash):
    async with async_timeout.timeout(30):
        while True:
            try:
                confirmations = (await wallet.server.get_tx_status(tx_hash))["confirmations"]
                if confirmations >= 1:
                    break
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(1)
    await asyncio.sleep(3)


async def send_to_address(address, amount, confirm=False, wait_balance=False):
    tx_hash = utils.run_shell(["sendtoaddress", address, str(amount)])
    if confirm:
        utils.run_shell(["newblocks", "1"])
    if wait_balance:
        await wait_for_balance(address, Decimal(amount))
    return tx_hash


def find_channel(channels, channel_point):
    for channel in channels:
        if channel["channel_point"] == channel_point:
            return channel


async def wait_for_channel_opening(regtest_wallet, channel_point):
    while True:
        channels = await regtest_wallet.list_channels()
        channel = find_channel(channels, channel_point)
        await asyncio.sleep(1)
        if channel["state"] == "OPEN":
            break
    await asyncio.sleep(1)


@pytest.fixture
async def regtest_wallet():
    return BTC(xpub=REGTEST_XPUB)


@pytest.fixture
async def regtest_lnnode():
    return BTC(xpub=REGTEST_XPUB2, rpc_url="http://localhost:5110")


@pytest.fixture
async def prepare_ln_channels(regtest_wallet, regtest_lnnode):
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
    await regtest_wallet.lnpay(invoice)
    yield
    await regtest_wallet.close_channel(channel_point)


@pytest.fixture
def queue():
    return multiprocessing.Queue()


@pytest.fixture
async def ipn_server(queue, client, token):
    host = "0.0.0.0"
    port = 8080

    async def handle_post(request):
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


def check_status(queue, data):
    queue_data = queue.get()
    assert queue_data[0] == data
    assert queue_data[0]["status"] == queue_data[1]


@pytest.fixture
async def regtest_api_wallet(client, user, token, anyio_backend):
    return await create_wallet(client, user["id"], token, xpub=REGTEST_XPUB)


@pytest.fixture
async def regtest_api_store(client, user, token, regtest_api_wallet, anyio_backend):
    return await create_store(client, user["id"], token, custom_store_attrs={"wallets": [regtest_api_wallet["id"]]})


@pytest.mark.parametrize("speed", range(MAX_CONFIRMATION_WATCH + 1))
async def test_onchain_pay_flow(client, ws_client, regtest_api_store, token, worker, queue, ipn_server, speed):
    store_id = regtest_api_store["id"]
    resp = await client.patch(
        f"/stores/{store_id}/checkout_settings",
        json={"transaction_speed": speed},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["checkout_settings"]["transaction_speed"] == speed
    invoice = (await client.post("/invoices", json={"price": 5, "store_id": store_id, "notification_url": ipn_server})).json()
    assert invoice["status"] == "pending"
    pay_details = invoice["payments"][0]
    address = pay_details["payment_address"]
    amount = pay_details["amount"]
    await send_to_address(address, amount)
    invoice_id = invoice["id"]
    zeroconf = speed == 0
    expected_status = "complete" if zeroconf else "paid"
    await check_invoice_status(
        ws_client, invoice_id, expected_status, sent_amount=amount, exception_status="none", allow_next=zeroconf
    )


async def test_exception_statuses(client, ws_client, regtest_api_store, token, worker, ipn_server):
    store_id = regtest_api_store["id"]
    invoice = (await client.post("/invoices", json={"price": 5, "store_id": store_id})).json()
    pay_details = invoice["payments"][0]
    address = pay_details["payment_address"]
    amount = Decimal(pay_details["amount"])
    part1 = truncate(amount / 2, 8)
    part2 = amount - part1
    await asyncio.sleep(3)  # wait for the worker startup (remove when electrum fixes pending tx_hashes returning)
    await send_to_address(address, part1)
    invoice_id = invoice["id"]
    await check_invoice_status(ws_client, invoice_id, "pending", exception_status="paid_partial", sent_amount=part1)
    await send_to_address(address, part2)
    await check_invoice_status(
        ws_client, invoice_id, "complete", exception_status="none", sent_amount=pay_details["amount"], allow_next=True
    )


async def test_lightning_pay_flow(
    client,
    ws_client,
    regtest_api_wallet,
    regtest_api_store,
    token,
    worker,
    queue,
    ipn_server,
    prepare_ln_channels,
    regtest_lnnode,
):
    wallet_id = regtest_api_wallet["id"]
    store_id = regtest_api_store["id"]
    resp = await client.patch(
        f"/wallets/{wallet_id}",
        json={"lightning_enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["lightning_enabled"]
    invoice = (await client.post("/invoices", json={"price": 5, "store_id": store_id, "notification_url": ipn_server})).json()
    assert invoice["status"] == "pending"
    pay_details = invoice["payments"][1]  # lightning methods are always created after onchain ones
    await regtest_lnnode.lnpay(pay_details["payment_address"])
    invoice_id = invoice["id"]
    await check_invoice_status(ws_client, invoice_id, "complete", exception_status="none", sent_amount=pay_details["amount"])
    assert queue.qsize() == 1
    check_status(queue, {"id": invoice["id"], "status": "complete"})
    # check that it was paid with lightning actually
    resp = await client.get(f"/invoices/{invoice_id}")
    assert resp.json()["paid_currency"] == "BTC (⚡)"


async def apply_batch_payout_action(client, token, command, ids, options={}):
    resp = await client.post(
        "/payouts/batch",
        json={"command": command, "ids": ids, "options": options},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() is True


async def check_payout_status(client, token, obj_id, expected_status):
    resp = await client.get(f"/payouts/{obj_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == expected_status


async def test_payouts(client, regtest_wallet, regtest_api_wallet, regtest_api_store, user, token, worker, queue, ipn_server):
    wallet_id = regtest_api_wallet["id"]
    store_id = regtest_api_store["id"]
    address = (await regtest_wallet.add_request())["address"]
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
    watchonly_wallet = await create_wallet(client, user["id"], token, xpub=xpub)
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
