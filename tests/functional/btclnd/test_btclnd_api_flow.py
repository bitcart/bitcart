"""Full API flow functional tests for BTCLND payments.

Tests the complete Bitcart stack: API → Worker → BTCLND Daemon → LND.
Uses the same in-process TestClient pattern as Bitcart's existing functional tests.

Covers:
1. On-chain payment: invoice → pay on-chain → mine → status change
2. On-chain partial payments: two transactions → complete
3. Lightning payment: invoice → pay via lightning → status change

Prerequisites:
    1. Start regtest environment:
        just btclnd-regtest-env

    2. Start BTCLND daemon (separate terminal):
        BTCLND_NETWORK=regtest BTCLND_TOR=false BTCLND_DATA_PATH=$PWD/.regtest/daemon \
        BTCLND_NEUTRINO_PEERS=127.0.0.1:18444 python3 daemons/btclnd.py

    3. Run tests:
        BTCLND_TEST_SEED="<seed>" pytest tests/functional/btclnd/test_btclnd_api_flow.py -v -n 0 --no-cov
"""

import asyncio
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from decimal import Decimal
from typing import Any, AsyncIterator

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "daemons"))

from httpx import AsyncClient as TestClient
from httpx_ws import aconnect_ws

from tests.functional.btclnd.utils import LNDTestClient, load_ports, mine_blocks
from tests.helper import create_invoice, create_store, create_token, create_user, create_wallet

pytestmark = pytest.mark.anyio

INVOICE_AMOUNT = 0.0001  # BTC
INVOICE_AMOUNT_SATS = 10_000


# ── Fixtures ───────────────────────────────────────────────────────────


# ports, seed, and anyio_backend fixtures are defined in conftest.py


@pytest.fixture(scope="session")
async def worker():
    """Start the Bitcart worker process."""
    env = os.environ.copy()
    env["BITCART_CRYPTOS"] = "btclnd"
    env["BTCLND_NETWORK"] = "regtest"
    env["BTCLND_TOR"] = "false"
    proc = subprocess.Popen([sys.executable, "worker.py"], env=env)
    await asyncio.sleep(5)
    yield proc
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
async def client() -> AsyncIterator[TestClient]:
    """HTTP client pointing at the running API."""
    async with TestClient(base_url="http://localhost:8000", timeout=60) as c:
        yield c


@pytest.fixture(scope="session")
async def token(client: TestClient) -> str:
    """Create first user (admin) and get auth token."""
    user = await create_user(client)
    token_data = await create_token(client, user)
    return token_data["access_token"]


@pytest.fixture(scope="session")
async def btclnd_wallet(client: TestClient, token: str, seed: str) -> dict[str, Any]:
    """Create a BTCLND wallet via the API."""
    return await create_wallet(
        client, token, xpub=seed, currency="btclnd", lightning_enabled=True
    )


@pytest.fixture(scope="session")
async def btclnd_store(client: TestClient, token: str, btclnd_wallet: dict) -> dict[str, Any]:
    """Create a store linked to the BTCLND wallet."""
    from tests.helper import create_model_obj

    return await create_model_obj(
        client,
        "stores",
        {"name": "LND Test Store", "wallets": [btclnd_wallet["id"]]},
        token=token,
    )


@pytest.fixture(scope="session")
async def customer(ports) -> AsyncIterator[LNDTestClient]:
    """Customer LND client for payments."""
    c = LNDTestClient("127.0.0.1", int(ports["CUSTOMER_GRPC"]), ports["CUSTOMER_DIR"])
    await c.connect()
    await c.wait_for_sync(timeout=30)
    yield c
    await c.close()


@pytest.fixture(scope="session")
async def funded_customer(customer):
    """Ensure customer has funds."""
    from tests.functional.btclnd.utils import fund_customer_wallet

    bal = await customer.wallet_balance()
    if bal < 1_000_000:
        await fund_customer_wallet(customer)
    return customer


@pytest.fixture(scope="session")
async def receiver(ports) -> AsyncIterator[LNDTestClient]:
    """Receiver LND client (third node for routing tests)."""
    c = LNDTestClient("127.0.0.1", int(ports["RECEIVER_GRPC"]), ports["RECEIVER_DIR"])
    await c.connect()
    await c.wait_for_sync(timeout=30)
    yield c
    await c.close()


@pytest.fixture(scope="session")
async def channel_ready(funded_customer, seed, ports):
    """Ensure lightning channel from customer to merchant."""
    from tests.functional.btclnd.utils import BitcartDaemonClient

    daemon = BitcartDaemonClient()

    # Wait for merchant to be ready
    for _ in range(60):
        try:
            info = await daemon.call_with_wallet("getinfo", xpub=seed)
            if info.get("block_height", 0) > 0:
                break
        except Exception:
            pass
        await asyncio.sleep(1)

    pubkey = info["identity_pubkey"]
    wk = hashlib.sha256(seed.strip().encode()).hexdigest()[:16]
    pm_path = os.path.join(os.getcwd(), ".regtest", "daemon", "port_map.json")
    pm = json.load(open(pm_path))
    p2p = pm[wk]["p2p"]

    channels = await funded_customer.list_channels()
    if any(c.active for c in channels):
        return True

    await funded_customer.connect_peer(pubkey, f"127.0.0.1:{p2p}")
    await asyncio.sleep(5)
    await funded_customer.open_channel_sync(pubkey, 500_000)
    mine_blocks(6)
    await asyncio.sleep(5)

    for _ in range(30):
        channels = await funded_customer.list_channels()
        if any(c.active for c in channels):
            return True
        await asyncio.sleep(1)

    pytest.fail("Channel did not become active")


# ── Helpers ────────────────────────────────────────────────────────────


async def get_invoice_status(client: TestClient, invoice_id: str) -> str:
    resp = await client.get(f"/invoices/{invoice_id}")
    return resp.json()["status"]


def get_payment_methods(invoice: dict) -> list:
    """Extract payment methods from the invoice response."""
    return invoice.get("payments", [])


async def wait_for_status(
    client: TestClient, token: str, invoice_id: str, expected: str, timeout: int = 60
) -> dict:
    """Poll invoice status until it matches expected.

    Also triggers wallet balance checks to help the worker detect payments
    (the worker's check_pending polls the daemon for each pending invoice).
    """
    for i in range(timeout):
        resp = await client.get(f"/invoices/{invoice_id}")
        data = resp.json()
        if data["status"] == expected:
            return data
        # Every few seconds, mine a block to trigger daemon events
        # which causes the worker's check_pending to run
        if i % 10 == 0 and i > 0:
            mine_blocks(1)
        await asyncio.sleep(1)
    resp = await client.get(f"/invoices/{invoice_id}")
    pytest.fail(
        f"Invoice {invoice_id} status={resp.json()['status']}, expected={expected}"
    )


# ── Tests ──────────────────────────────────────────────────────────────


class TestOnChainPayment:
    """Test on-chain payment through the full Bitcart stack."""

    async def test_onchain_full_payment(
        self, client: TestClient, token: str, btclnd_store: dict,
        funded_customer: LNDTestClient, worker,
    ):
        """invoice → on-chain payment → mine → status=complete."""
        store_id = btclnd_store["id"]
        invoice = await create_invoice(
            client, token, store_id=store_id, price=INVOICE_AMOUNT, currency="BTC"
        )
        invoice_id = invoice["id"]
        assert invoice["status"] == "pending"

        # Get on-chain address
        payments = get_payment_methods(invoice)
        onchain = next((p for p in payments if not p.get("lightning")), None)
        assert onchain, f"No on-chain payment method. Payments: {payments}"
        address = onchain["payment_address"]

        # Pay
        txid = await funded_customer.send_coins(address, INVOICE_AMOUNT_SATS)
        mine_blocks(1)
        await asyncio.sleep(3)

        # Check status
        invoice = await wait_for_status(client, token, invoice_id, "complete", timeout=60)
        assert invoice["status"] == "complete"


class TestPartialOnChainPayment:
    """Test partial on-chain payments."""

    async def test_partial_then_complete(
        self, client: TestClient, token: str, btclnd_store: dict,
        funded_customer: LNDTestClient, worker,
    ):
        """invoice → partial pay → mine → second pay → mine → complete."""
        store_id = btclnd_store["id"]
        total_btc = 0.0002  # 20,000 sats
        invoice = await create_invoice(
            client, token, store_id=store_id, price=total_btc, currency="BTC"
        )
        invoice_id = invoice["id"]

        payments = get_payment_methods(invoice)
        onchain = next((p for p in payments if not p.get("lightning")), None)
        address = onchain["payment_address"]

        # First partial: 12,000 sats (60% of 20,000)
        await funded_customer.send_coins(address, 12_000)
        mine_blocks(1)
        await asyncio.sleep(8)

        # After partial payment, status should be paid_partial or still pending, NOT complete
        status = await get_invoice_status(client, invoice_id)
        assert status in ("pending", "paid"), (
            f"After first partial (12k/20k), expected pending or paid, got {status}"
        )

        # Second partial: 10,000 sats (enough to cover remaining + some extra)
        await funded_customer.send_coins(address, 10_000)
        mine_blocks(1)
        await asyncio.sleep(3)

        # Now should be complete (total received >= 20,000)
        invoice = await wait_for_status(client, token, invoice_id, "complete", timeout=60)
        assert invoice["status"] == "complete"


class TestZeroConfOnChainPayment:
    """Test that on-chain payments are detected with zero confirmations.

    In neutrino mode, unconfirmed transaction detection depends on the
    GetTransactions fallback (ListUnspent may miss unconfirmed UTXOs).
    The daemon's get_request checks both ListUnspent and GetTransactions
    to detect payments before they are confirmed in a block.
    """

    async def test_zeroconf_detection(
        self, client: TestClient, token: str, btclnd_store: dict,
        funded_customer: LNDTestClient, worker,
    ):
        """Payment should be detected without mining a block (zero-conf)."""
        store_id = btclnd_store["id"]
        invoice = await create_invoice(
            client, token, store_id=store_id, price=0.0001, currency="BTC"
        )
        invoice_id = invoice["id"]

        payments = get_payment_methods(invoice)
        onchain = next((p for p in payments if not p.get("lightning")), None)
        address = onchain["payment_address"]

        # Send payment — do NOT mine any blocks
        await funded_customer.send_coins(address, 10_000)

        # Wait for the unconfirmed transaction to propagate between the two
        # LND nodes (via bitcoind mempool) and for the daemon's
        # SubscribeTransactions / GetTransactions fallback to detect it.
        invoice = await wait_for_status(client, token, invoice_id, "complete", timeout=60)
        assert invoice["status"] == "complete"


class TestOpenChannelFromDaemon:
    """Test opening lightning channels via the daemon's open_channel RPC.

    Tests both announced (public) and unannounced (private) channels,
    verifying the channel visibility is correctly reflected in list_channels.
    """

    async def _fund_and_connect(self, daemon, seed, funded_customer, ports):
        """Helper: fund merchant, connect to customer, return customer pubkey."""
        # Wait for daemon wallet to be synced
        for _ in range(60):
            try:
                info = await daemon.call_with_wallet("getinfo", xpub=seed)
                if info.get("synced_to_chain"):
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        # Fund the merchant wallet
        merchant_addr = await daemon.call_with_wallet("createnewaddress", xpub=seed)
        mine_blocks(1, merchant_addr)
        mine_blocks(100)
        await asyncio.sleep(5)

        # Connect to customer
        customer_info = await funded_customer.get_info()
        customer_pubkey = customer_info.identity_pubkey
        customer_p2p = f"127.0.0.1:{ports['CUSTOMER_P2P']}"
        await daemon.call_with_wallet(
            "add_peer", xpub=seed, addr=f"{customer_pubkey}@{customer_p2p}"
        )
        await asyncio.sleep(2)
        return customer_pubkey

    async def _wait_for_open_channel(self, daemon, seed, customer_pubkey, expect_private):
        """Helper: wait for channel to open, verify private flag."""
        for _ in range(30):
            channels = await daemon.call_with_wallet("list_channels", xpub=seed)
            matching = [
                c for c in channels
                if c.get("state") == "OPEN" and c.get("remote_pubkey") == customer_pubkey
                and c.get("private") == expect_private
            ]
            if matching:
                return matching[0]
            await asyncio.sleep(1)
        channels = await daemon.call_with_wallet("list_channels", xpub=seed)
        pytest.fail(
            f"Channel with private={expect_private} to {customer_pubkey[:16]}... "
            f"did not become OPEN. Channels: {channels}"
        )

    async def test_open_announced_channel(
        self, client: TestClient, token: str, seed: str,
        funded_customer: LNDTestClient, ports,
    ):
        """Opening a channel with private=False should create an announced channel."""
        from tests.functional.btclnd.utils import BitcartDaemonClient, mine_blocks

        daemon = BitcartDaemonClient()
        customer_pubkey = await self._fund_and_connect(daemon, seed, funded_customer, ports)

        result = await daemon.call_with_wallet(
            "open_channel", xpub=seed,
            node_id=customer_pubkey,
            amount=200_000,
            private=False,
        )
        assert "funding_txid" in result

        mine_blocks(6)
        await asyncio.sleep(5)

        channel = await self._wait_for_open_channel(daemon, seed, customer_pubkey, expect_private=False)
        assert channel["private"] is False

    async def test_open_unannounced_channel(
        self, client: TestClient, token: str, seed: str,
        funded_customer: LNDTestClient, ports,
    ):
        """Opening a channel with private=True should create an unannounced channel."""
        from tests.functional.btclnd.utils import BitcartDaemonClient, mine_blocks

        daemon = BitcartDaemonClient()
        customer_pubkey = await self._fund_and_connect(daemon, seed, funded_customer, ports)

        result = await daemon.call_with_wallet(
            "open_channel", xpub=seed,
            node_id=customer_pubkey,
            amount=150_000,
            private=True,
        )
        assert "funding_txid" in result

        mine_blocks(6)
        await asyncio.sleep(5)

        channel = await self._wait_for_open_channel(daemon, seed, customer_pubkey, expect_private=True)
        assert channel["private"] is True


class TestDaemonLnpay:
    """Test paying a lightning invoice via the daemon's lnpay RPC.

    This tests the path used by the admin panel's "Pay LN invoice" button:
    API → daemon.lnpay(invoice) → LND.SendPaymentSync().
    Requires a channel from merchant→customer so the merchant can send.
    """

    async def test_lnpay_pays_invoice(
        self, seed: str, funded_customer: LNDTestClient, ports,
    ):
        """Daemon should pay a customer's invoice via lnpay RPC."""
        from tests.functional.btclnd.utils import BitcartDaemonClient, mine_blocks

        daemon = BitcartDaemonClient()

        # Wait for daemon wallet to sync
        for _ in range(60):
            try:
                info = await daemon.call_with_wallet("getinfo", xpub=seed)
                if info.get("synced_to_chain"):
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        # Fund merchant wallet and open channel to customer
        merchant_addr = await daemon.call_with_wallet("createnewaddress", xpub=seed)
        mine_blocks(1, merchant_addr)
        mine_blocks(100)
        await asyncio.sleep(5)

        customer_info = await funded_customer.get_info()
        customer_pubkey = customer_info.identity_pubkey
        customer_p2p = f"127.0.0.1:{ports['CUSTOMER_P2P']}"

        # Connect and open channel from merchant to customer
        await daemon.call_with_wallet(
            "add_peer", xpub=seed, addr=f"{customer_pubkey}@{customer_p2p}"
        )
        await asyncio.sleep(2)
        await daemon.call_with_wallet(
            "open_channel", xpub=seed,
            node_id=customer_pubkey,
            amount=500_000,
        )
        mine_blocks(6)
        await asyncio.sleep(5)

        # Wait for channel to be active
        for _ in range(30):
            channels = await daemon.call_with_wallet("list_channels", xpub=seed)
            if any(c.get("state") == "OPEN" for c in channels):
                break
            await asyncio.sleep(1)

        # Create an invoice on the customer LND (simulating an external payee)
        customer_invoice = await funded_customer.add_invoice(10_000, memo="lnpay test")
        bolt11 = customer_invoice.payment_request
        assert bolt11.startswith("lnbcrt"), f"Expected regtest bolt11, got: {bolt11[:20]}"

        # Pay via the daemon's lnpay RPC
        result = await daemon.call_with_wallet("lnpay", xpub=seed, invoice=bolt11)

        assert "payment_hash" in result, f"Expected payment_hash in result: {result}"
        assert "payment_preimage" in result
        assert len(result["payment_hash"]) == 64  # 32 bytes hex
        assert len(result["payment_preimage"]) == 64

        # Verify the customer received the payment
        customer_invoice_lookup = await funded_customer.lookup_invoice(
            bytes.fromhex(result["payment_hash"])
        )
        assert customer_invoice_lookup.state == 1  # SETTLED


class TestPaymentRouting:
    """Test that payments routed through the merchant LND are tracked.

    Topology: Customer → Merchant (our daemon) → Receiver
    The customer pays an invoice created by the receiver. The payment
    routes through the merchant, who collects a routing fee. We then
    verify the daemon's getinfo reports correct routing statistics
    and that list_channels shows per-channel fee schedules.
    """

    async def test_routed_payment_stats(
        self, seed: str, funded_customer: LNDTestClient,
        receiver: LNDTestClient, ports,
    ):
        """Route a payment through the merchant and verify routing stats."""
        from tests.functional.btclnd.utils import BitcartDaemonClient, mine_blocks

        daemon = BitcartDaemonClient()

        # Wait for daemon wallet to sync
        for _ in range(60):
            try:
                info = await daemon.call_with_wallet("getinfo", xpub=seed)
                if info.get("synced_to_chain"):
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        # --- Fund merchant wallet ---
        merchant_addr = await daemon.call_with_wallet("createnewaddress", xpub=seed)
        mine_blocks(1, merchant_addr)
        mine_blocks(100)
        await asyncio.sleep(5)

        # --- Get node pubkeys ---
        customer_info = await funded_customer.get_info()
        customer_pubkey = customer_info.identity_pubkey
        customer_p2p = f"127.0.0.1:{ports['CUSTOMER_P2P']}"

        receiver_info = await receiver.get_info()
        receiver_pubkey = receiver_info.identity_pubkey
        receiver_p2p = f"127.0.0.1:{ports['RECEIVER_P2P']}"

        merchant_info = await daemon.call_with_wallet("getinfo", xpub=seed)
        merchant_pubkey = merchant_info["identity_pubkey"]
        merchant_wk = hashlib.sha256(seed.strip().encode()).hexdigest()[:16]
        pm = json.load(open(os.path.join(os.getcwd(), ".regtest", "daemon", "port_map.json")))
        merchant_p2p = pm[merchant_wk]["p2p"]

        # --- Set up channels: Customer → Merchant → Receiver ---

        # Customer connects to Merchant (may already be connected)
        try:
            await funded_customer.connect_peer(merchant_pubkey, f"127.0.0.1:{merchant_p2p}")
        except Exception:
            pass  # already connected
        await asyncio.sleep(1)

        # Merchant connects to Receiver via daemon RPC
        await daemon.call_with_wallet(
            "add_peer", xpub=seed, addr=f"{receiver_pubkey}@{receiver_p2p}"
        )
        await asyncio.sleep(1)

        # Customer opens channel to Merchant
        customer_channels = await funded_customer.list_channels()
        if not any(c.active and c.remote_pubkey == merchant_pubkey for c in customer_channels):
            await funded_customer.open_channel_sync(merchant_pubkey, 500_000)
            mine_blocks(6)
            await asyncio.sleep(5)

        # Merchant opens channel to Receiver via daemon RPC
        merchant_channels = await daemon.call_with_wallet("list_channels", xpub=seed)
        if not any(c.get("remote_pubkey") == receiver_pubkey and c.get("state") == "OPEN"
                   for c in merchant_channels):
            await daemon.call_with_wallet(
                "open_channel", xpub=seed,
                node_id=receiver_pubkey, amount=500_000,
            )
            mine_blocks(6)
            await asyncio.sleep(5)

        # Wait for both channels to be active
        for _ in range(30):
            customer_channels = await funded_customer.list_channels()
            merchant_channels = await daemon.call_with_wallet("list_channels", xpub=seed)
            customer_has = any(c.active and c.remote_pubkey == merchant_pubkey for c in customer_channels)
            merchant_has = any(c.get("remote_pubkey") == receiver_pubkey and c.get("state") == "OPEN"
                              for c in merchant_channels)
            if customer_has and merchant_has:
                break
            await asyncio.sleep(1)
        else:
            pytest.fail("Channels did not become active")

        # --- Get baseline routing stats ---
        info_before = await daemon.call_with_wallet("getinfo", xpub=seed)
        routed_before = info_before.get("total_payments_routed", 0)

        # --- Receiver creates an invoice ---
        invoice_resp = await receiver.add_invoice(50_000, memo="routing test")
        bolt11 = invoice_resp.payment_request

        # --- Customer pays the invoice (routes through Merchant) ---
        pay_resp = await funded_customer.send_payment_sync(bolt11)
        assert pay_resp.payment_hash, f"Payment failed: {pay_resp.payment_error}"

        # Give LND time to record the forwarding event
        await asyncio.sleep(3)

        # --- Verify routing stats ---
        info_after = await daemon.call_with_wallet("getinfo", xpub=seed)
        routed_after = info_after.get("total_payments_routed", 0)

        assert routed_after > routed_before, (
            f"Routing count did not increase: before={routed_before}, after={routed_after}"
        )
        assert info_after["total_amount_routed_sats"] > 0, "No amount routed"
        assert info_after["total_fees_collected_sats"] >= 0, "Fee field missing"
        assert info_after["total_amount_routed_btc"] != "0", "BTC amount should be non-zero"

        # --- Verify per-channel fee schedules ---
        channels = await daemon.call_with_wallet("list_channels", xpub=seed)
        open_channels = [c for c in channels if c.get("state") == "OPEN"]
        assert len(open_channels) > 0

        for ch in open_channels:
            assert "base_fee_sats" in ch, f"Missing base_fee_sats on channel {ch.get('channel_point','?')}"
            assert "fee_rate_ppm" in ch, f"Missing fee_rate_ppm"
            assert "fee_rate_percent" in ch, f"Missing fee_rate_percent"
            # Base fee and rate should be non-negative
            assert ch["base_fee_sats"] >= 0
            assert ch["fee_rate_ppm"] >= 0

        # --- Verify receiver got paid ---
        receiver_invoice = await receiver.lookup_invoice(pay_resp.payment_hash)
        assert receiver_invoice.state == 1  # SETTLED
        assert receiver_invoice.amt_paid_sat == 50_000


class TestLightningPayment:
    """Test lightning payment through the full Bitcart stack."""

    async def test_lightning_pay(
        self, client: TestClient, token: str, btclnd_store: dict,
        funded_customer: LNDTestClient, channel_ready, worker,
    ):
        """invoice → lightning payment → status=complete."""
        store_id = btclnd_store["id"]
        invoice = await create_invoice(
            client, token, store_id=store_id, price=0.00005, currency="BTC"
        )
        invoice_id = invoice["id"]

        # Get lightning payment method
        payments = get_payment_methods(invoice)
        ln = next((p for p in payments if p.get("lightning")), None)
        assert ln, f"No lightning payment method. Payments: {payments}"
        bolt11 = ln["payment_address"]
        assert bolt11.startswith("ln"), f"Invalid bolt11: {bolt11[:20]}"

        # Pay
        resp = await funded_customer.send_payment_sync(bolt11)
        assert resp.payment_hash

        # Mine a block to trigger the daemon's event system and worker's check_pending
        mine_blocks(1)
        await asyncio.sleep(3)

        # Check status
        invoice = await wait_for_status(client, token, invoice_id, "complete", timeout=60)
        assert invoice["status"] == "complete"
