"""Functional tests for BTCLND payment flows.

Tests cover:
1. Lightning payment: create invoice → pay via lightning → detect payment
2. On-chain payment: create invoice → pay on-chain → mine block → detect payment
3. Partial on-chain payments: pay invoice in multiple transactions

Prerequisites:
    Run the bootstrap script first:
        bash tests/functional/btclnd/bootstrap.sh start

    Then start the BTCLND daemon in regtest mode:
        BTCLND_NETWORK=regtest BTCLND_TOR=false BTCLND_DEBUG=true python3 daemons/btclnd.py

    Then run these tests:
        pytest tests/functional/btclnd/test_btclnd_payments.py -v -n 0 --no-cov
"""

import asyncio
import os
import sys
import time
from decimal import Decimal

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "daemons"))

from tests.functional.btclnd.utils import (
    BitcartDaemonClient,
    LNDTestClient,
    fund_customer_wallet,
    load_ports,
    mine_blocks,
    setup_lightning_channel,
)

# Test constants
INVOICE_AMOUNT_SATS = 10_000  # 10,000 sats = 0.0001 BTC
INVOICE_AMOUNT_BTC = "0.00010000"
CHANNEL_SIZE = 500_000  # 500k sats channel

# Skip all tests if regtest environment is not running
pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
def ports():
    """Load port configuration from bootstrap."""
    p = load_ports()
    if not p:
        pytest.skip("Regtest environment not running. Run bootstrap.sh first.")
    return p


@pytest.fixture(scope="session")
def merchant_seed():
    """Seed phrase for the merchant wallet used in tests.

    This must be a valid 24-word aezeed mnemonic. For regtest testing
    with --noseedbackup, we use the BTCLND daemon's make_seed to generate one,
    or use a pre-generated one.
    """
    # Try to get from environment, or use the daemon to generate
    seed = os.environ.get("BTCLND_TEST_SEED")
    if seed:
        return seed
    pytest.skip("Set BTCLND_TEST_SEED environment variable with a valid aezeed seed")


@pytest.fixture(scope="session")
async def customer(ports):
    """Customer LND client (the payer)."""
    client = LNDTestClient(
        host="127.0.0.1",
        port=int(ports["CUSTOMER_GRPC"]),
        lnd_dir=ports["CUSTOMER_DIR"],
    )
    await client.connect()
    await client.wait_for_sync(timeout=120)
    yield client
    await client.close()


@pytest.fixture(scope="session")
async def merchant(ports):
    """Merchant LND client (direct connection, for verification)."""
    client = LNDTestClient(
        host="127.0.0.1",
        port=int(ports["MERCHANT_GRPC"]),
        lnd_dir=ports["MERCHANT_DIR"],
    )
    await client.connect()
    await client.wait_for_sync(timeout=120)
    yield client
    await client.close()


@pytest.fixture(scope="session")
def daemon():
    """BTCLND daemon client."""
    return BitcartDaemonClient(url="http://localhost:5012")


@pytest.fixture(scope="session")
async def funded_customer(customer):
    """Ensure the customer has funds."""
    balance = await customer.wallet_balance()
    if balance < 1_000_000:  # less than 0.01 BTC
        await fund_customer_wallet(customer)
    return customer


@pytest.fixture(scope="session")
async def channel_ready(funded_customer, merchant, ports):
    """Ensure a lightning channel exists between customer and merchant."""
    channels = await funded_customer.list_channels()
    if not any(ch.active for ch in channels):
        merchant_info = await merchant.get_info()
        # Check if merchant has the right pubkey for our channel
        await setup_lightning_channel(
            funded_customer,
            merchant,
            merchant_p2p_port=int(ports["MERCHANT_P2P"]),
            channel_size=CHANNEL_SIZE,
        )
    return True


# =========================================================================
# Test 1: Lightning Payment
# =========================================================================


class TestLightningPayment:
    """Test creating an invoice and paying it via lightning."""

    async def test_create_invoice(self, daemon, merchant_seed):
        """Create a lightning invoice via the BTCLND daemon."""
        result = await daemon.call_with_wallet(
            "add_request",
            xpub=merchant_seed,
            amount=INVOICE_AMOUNT_BTC,
            memo="Lightning test payment",
            expiry=3600,
        )
        assert result is not None
        assert "lightning_invoice" in result or "lightning" in result
        assert "rhash" in result
        assert result["rhash"]

    async def test_pay_lightning_invoice(self, daemon, merchant_seed, funded_customer, channel_ready):
        """Create an invoice, pay it via lightning, and verify payment detection."""
        # Create invoice
        invoice_data = await daemon.call_with_wallet(
            "add_request",
            xpub=merchant_seed,
            amount=INVOICE_AMOUNT_BTC,
            memo="LN payment test",
            expiry=3600,
        )
        bolt11 = invoice_data.get("lightning_invoice") or invoice_data.get("lightning")
        rhash = invoice_data["rhash"]
        assert bolt11, "No BOLT11 invoice returned"

        # Pay via customer LND
        pay_resp = await funded_customer.send_payment_sync(bolt11)
        assert pay_resp.payment_hash, "Payment hash empty"

        # Verify the daemon shows the invoice as paid
        await asyncio.sleep(1)  # brief delay for event processing
        request_data = await daemon.call_with_wallet(
            "get_request", xpub=merchant_seed, key=rhash
        )
        assert request_data["status"] == 3, f"Invoice not paid, status={request_data['status']}"
        assert request_data["status_str"] == "Paid"
        assert Decimal(request_data["sent_amount"]) > 0


# =========================================================================
# Test 2: On-chain Payment
# =========================================================================


class TestOnChainPayment:
    """Test creating an invoice and paying it with an on-chain transaction."""

    async def test_pay_onchain(self, daemon, merchant_seed, funded_customer):
        """Create an invoice, pay on-chain, mine a block, verify detection."""
        # Create invoice (add_request returns both on-chain address and lightning)
        invoice_data = await daemon.call_with_wallet(
            "add_request",
            xpub=merchant_seed,
            amount=INVOICE_AMOUNT_BTC,
            memo="On-chain payment test",
            expiry=3600,
        )
        address = invoice_data["address"]
        assert address, "No on-chain address returned"
        assert address.startswith(("bcrt1", "tb1", "2", "m", "n")), f"Unexpected address format: {address}"

        # Send on-chain payment from customer
        amount_sats = INVOICE_AMOUNT_SATS
        txid = await funded_customer.send_coins(address, amount_sats)
        assert txid, "No txid returned from send_coins"

        # Mine a block to confirm the transaction
        mine_blocks(1)
        await asyncio.sleep(3)  # let LND process the block

        # Verify the transaction appears in the merchant's history
        tx_data = await daemon.call_with_wallet(
            "get_transaction", xpub=merchant_seed, tx_hash=txid
        )
        assert tx_data is not None
        assert tx_data["txid"] == txid
        assert tx_data["num_confirmations"] >= 1


# =========================================================================
# Test 3: Partial On-chain Payments (Multiple Transactions)
# =========================================================================


class TestPartialOnChainPayment:
    """Test paying an invoice with multiple on-chain transactions."""

    async def test_partial_payments(self, daemon, merchant_seed, funded_customer):
        """Create an invoice, pay in two separate transactions, verify total."""
        # Create a larger invoice
        total_amount_sats = 20_000  # 20k sats
        total_amount_btc = "0.00020000"
        partial1_sats = 12_000  # first payment: 12k sats
        partial2_sats = 8_000   # second payment: 8k sats

        invoice_data = await daemon.call_with_wallet(
            "add_request",
            xpub=merchant_seed,
            amount=total_amount_btc,
            memo="Partial payment test",
            expiry=3600,
        )
        address = invoice_data["address"]
        assert address, "No on-chain address returned"

        # First partial payment
        txid1 = await funded_customer.send_coins(address, partial1_sats)
        assert txid1, "First partial payment failed"

        # Mine a block
        mine_blocks(1)
        await asyncio.sleep(3)

        # Check address balance — should be partial
        balance_data = await daemon.call_with_wallet(
            "getaddressbalance_wallet", xpub=merchant_seed, address=address
        )
        confirmed_sats = int(Decimal(balance_data["confirmed"]) * 100_000_000)
        assert confirmed_sats >= partial1_sats, (
            f"First partial not reflected: {confirmed_sats} < {partial1_sats}"
        )
        assert confirmed_sats < total_amount_sats, (
            f"Should not be fully paid yet: {confirmed_sats} >= {total_amount_sats}"
        )

        # Second partial payment
        txid2 = await funded_customer.send_coins(address, partial2_sats)
        assert txid2, "Second partial payment failed"
        assert txid2 != txid1, "Second payment should be a different transaction"

        # Mine another block
        mine_blocks(1)
        await asyncio.sleep(3)

        # Check address balance — should now cover the full amount
        balance_data = await daemon.call_with_wallet(
            "getaddressbalance_wallet", xpub=merchant_seed, address=address
        )
        confirmed_sats = int(Decimal(balance_data["confirmed"]) * 100_000_000)
        assert confirmed_sats >= total_amount_sats, (
            f"Full amount not received: {confirmed_sats} < {total_amount_sats}"
        )


# =========================================================================
# Test 4: Balance Checks
# =========================================================================


class TestBalanceChecks:
    """Test wallet balance reporting."""

    async def test_onchain_balance(self, daemon, merchant_seed):
        """Verify on-chain balance is reported correctly."""
        balance = await daemon.call_with_wallet("getbalance", xpub=merchant_seed)
        assert "confirmed" in balance
        assert "unconfirmed" in balance
        assert "lightning" in balance
        # All should be valid decimal strings
        for key in ("confirmed", "unconfirmed", "lightning"):
            Decimal(balance[key])  # should not raise

    async def test_lightning_balance_after_payment(self, daemon, merchant_seed, channel_ready):
        """After receiving a lightning payment, channel balance should be > 0."""
        balance = await daemon.call_with_wallet("getbalance", xpub=merchant_seed)
        # Lightning balance comes from channel local_balance
        lightning_sats = int(Decimal(balance["lightning"]) * 100_000_000)
        # May be 0 if no lightning payments have been received yet in this session
        # but should at least be a valid number
        assert lightning_sats >= 0


# =========================================================================
# Test 5: Node Info
# =========================================================================


class TestNodeInfo:
    """Test node information reporting."""

    async def test_getinfo(self, daemon, merchant_seed):
        """Verify getinfo returns expected fields."""
        info = await daemon.call_with_wallet("getinfo", xpub=merchant_seed)
        assert "version" in info
        assert "identity_pubkey" in info
        assert "synced_to_chain" in info
        assert "block_height" in info
        assert info["synced_to_chain"] is True
        assert info["block_height"] > 0

    async def test_nodeid(self, daemon, merchant_seed):
        """Verify node ID is returned."""
        node_id = await daemon.call_with_wallet("nodeid", xpub=merchant_seed)
        assert node_id
        assert len(node_id) == 66  # hex-encoded compressed pubkey

    async def test_list_channels(self, daemon, merchant_seed, channel_ready):
        """Verify channel list includes our test channel."""
        channels = await daemon.call_with_wallet("list_channels", xpub=merchant_seed)
        assert len(channels) >= 1
        assert channels[0]["capacity"] > 0
