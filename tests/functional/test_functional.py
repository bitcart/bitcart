import asyncio
import multiprocessing
import signal
from decimal import Decimal

import pytest
from aiohttp import web
from bitcart import BTC

from api.constants import MAX_CONFIRMATION_WATCH
from tests.functional import utils
from tests.helper import create_store, create_wallet

REGTEST_XPUB = "dutch field mango comfort symptom smooth wide senior tongue oyster wash spoon"
REGTEST_XPUB2 = "hungry ordinary similar more spread math general wire jealous valve exhaust emotion"
LIGHTNING_CHANNEL_AMOUNT = Decimal("0.1")
LNPAY_AMOUNT = LIGHTNING_CHANNEL_AMOUNT / 10


@pytest.fixture
def worker():
    process = utils.start_worker()
    yield
    process.send_signal(signal.SIGINT)
    process.wait()


async def get_status(async_client, invoice_id):
    resp = await async_client.get(f"/invoices/{invoice_id}")
    assert resp.status_code == 200
    return resp.json()["status"]


async def wait_for_balance(address, expected_balance):
    wallet = BTC(xpub=address)
    while True:
        balance = await wallet.balance()
        balance = balance["confirmed"] + balance["unconfirmed"]
        await asyncio.sleep(1)
        if balance >= expected_balance:
            break
    await asyncio.sleep(3)


async def wait_for_confirmations(address, tx_hash, expected_confirmations):
    wallet = BTC(xpub=address)
    while True:
        # Note: we use get_tx_status instead of get_tx to get client-side confirmations
        # Server has confirmations instantly, it takes some time to deliver to client
        tx_data = await wallet.server.get_tx_status(tx_hash)
        await asyncio.sleep(1)
        if tx_data["confirmations"] >= expected_confirmations:
            break
    await asyncio.sleep(3)


async def send_to_address(address, amount, confirm=False):
    tx_hash = utils.run_shell(["sendtoaddress", address, str(amount)])
    if confirm:
        utils.run_shell(["newblocks", "1"])
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
    await send_to_address(address, fund_amount, confirm=True)
    channel_point = await regtest_wallet.open_channel(node_id, LIGHTNING_CHANNEL_AMOUNT)
    # make it fully open
    utils.run_shell(["newblocks", "3"])
    await wait_for_channel_opening(regtest_wallet, channel_point)
    # transfer some amount to the other node to be able to receive
    invoice = (await regtest_lnnode.add_invoice(LNPAY_AMOUNT))["invoice"]
    await regtest_wallet.lnpay(invoice)
    yield
    await regtest_wallet.close_channel(channel_point)


@pytest.fixture
def queue():
    return multiprocessing.Queue()


@pytest.fixture
async def ipn_server(queue, async_client):
    host = "0.0.0.0"
    port = 8080

    async def handle_post(request):
        data = await request.json()
        # to ensure status during IPN matches the one sent
        status = await get_status(async_client, data["id"])
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
def regtest_api_wallet(client, user, token):
    return create_wallet(client, user["id"], token, xpub=REGTEST_XPUB)


@pytest.fixture
def regtest_api_store(client, user, token, regtest_api_wallet):
    return create_store(client, user["id"], token, custom_store_attrs={"wallets": [regtest_api_wallet["id"]]})


@pytest.mark.parametrize("speed", range(MAX_CONFIRMATION_WATCH + 1))
@pytest.mark.anyio
async def test_onchain_pay_flow(async_client, regtest_api_store, token, worker, queue, ipn_server, speed):
    store_id = regtest_api_store["id"]
    resp = await async_client.patch(
        f"/stores/{store_id}/checkout_settings",
        json={"transaction_speed": speed},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["checkout_settings"]["transaction_speed"] == speed
    invoice = (
        await async_client.post("/invoices", json={"price": 5, "store_id": store_id, "notification_url": ipn_server})
    ).json()
    assert invoice["status"] == "pending"
    pay_details = invoice["payments"][0]
    address = pay_details["payment_address"]
    amount = pay_details["amount"]
    tx_hash = await send_to_address(address, amount)
    invoice_id = invoice["id"]
    status = await get_status(async_client, invoice_id)
    expected_status = "complete" if speed == 0 else "paid"
    assert status == expected_status
    if speed > 0:
        utils.run_shell(["newblocks", str(speed)])
        await wait_for_confirmations(address, tx_hash, speed)
        assert await get_status(async_client, invoice_id) == "complete"
    assert queue.qsize() == 2
    check_status(queue, {"id": invoice["id"], "status": "paid"})
    check_status(queue, {"id": invoice["id"], "status": "complete"})


@pytest.mark.anyio
async def test_lightning_pay_flow(
    async_client, regtest_api_wallet, regtest_api_store, token, worker, queue, ipn_server, prepare_ln_channels, regtest_lnnode
):
    wallet_id = regtest_api_wallet["id"]
    store_id = regtest_api_store["id"]
    resp = await async_client.patch(
        f"/wallets/{wallet_id}",
        json={"lightning_enabled": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["lightning_enabled"]
    invoice = (
        await async_client.post("/invoices", json={"price": 5, "store_id": store_id, "notification_url": ipn_server})
    ).json()
    assert invoice["status"] == "pending"
    pay_details = invoice["payments"][1]  # lightning methods are always created after onchain ones
    await regtest_lnnode.lnpay(pay_details["payment_address"])
    invoice_id = invoice["id"]
    status = await get_status(async_client, invoice_id)
    assert status == "complete"
    assert queue.qsize() == 1
    check_status(queue, {"id": invoice["id"], "status": "complete"})
