import asyncio
import multiprocessing
import signal
from decimal import Decimal

import pytest
from aiohttp import web
from bitcart import BTC

from api.constants import MAX_CONFIRMATION_WATCH
from tests.functional import utils


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
    await asyncio.sleep(1)


async def wait_for_confirmations(address, tx_hash, expected_confirmations):
    wallet = BTC(xpub=address)
    while True:
        # Note: we use get_tx_status instead of get_tx to get client-side confirmations
        # Server has confirmations instantly, it takes some time to deliver to client
        tx_data = await wallet.server.get_tx_status(tx_hash)
        await asyncio.sleep(1)
        if tx_data["confirmations"] >= expected_confirmations:
            break
    # Because we sleep in block processing code too
    await asyncio.sleep(5)


@pytest.fixture
def queue():
    return multiprocessing.Queue()


@pytest.fixture
async def ipn_server(queue):
    host = "0.0.0.0"
    port = 8080

    async def handle_post(request):
        queue.put(await request.json())
        return web.json_response({})

    app = web.Application()
    app.router.add_post("/", handle_post)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    yield f"http://{host}:{port}"
    await runner.cleanup()


@pytest.mark.parametrize("speed", range(MAX_CONFIRMATION_WATCH + 1))
@pytest.mark.asyncio
async def test_pay_flow(async_client, store, token, worker, queue, ipn_server, speed):
    store_id = store["id"]
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
    tx_hash = utils.run_shell(["sendtoaddress", address, amount])
    await wait_for_balance(address, Decimal(amount))
    invoice_id = invoice["id"]
    status = await get_status(async_client, invoice_id)
    expected_status = "complete" if speed == 0 else "paid"
    assert status == expected_status
    if speed > 0:
        utils.run_shell(["newblocks", str(speed)])
        await wait_for_confirmations(address, tx_hash, speed)
        assert await get_status(async_client, invoice_id) == "complete"
    assert queue.qsize() == 2
    assert queue.get() == {"id": invoice["id"], "status": "paid"}
    assert queue.get() == {"id": invoice["id"], "status": "complete"}
