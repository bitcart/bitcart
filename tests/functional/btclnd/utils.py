"""Utilities for BTCLND regtest functional tests.

Provides helper classes for interacting with bitcoind (mining blocks),
LND nodes (via gRPC), and the Bitcart API during testing.
"""

import asyncio
import codecs
import json
import os
import subprocess
import time

import grpc

# Add daemons to path for proto imports
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "daemons"))

from lnd_proto import (
    lightning_pb2,
    lightning_pb2_grpc,
    walletunlocker_pb2,
    walletunlocker_pb2_grpc,
)

# Test data directory is inside the project root
_PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..")
TEST_DIR = os.path.join(_PROJECT_DIR, ".regtest")
PORTS_FILE = os.path.join(TEST_DIR, "ports.env")


def load_ports() -> dict[str, str]:
    """Load port configuration from the bootstrap script's output."""
    ports = {}
    if os.path.exists(PORTS_FILE):
        with open(PORTS_FILE) as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    ports[key] = val
    return ports


def bitcoin_cli(*args: str) -> str:
    """Run bitcoin-cli with regtest credentials."""
    bitcoin_dir = os.path.join(TEST_DIR, "bitcoind")
    cmd = [
        "bitcoin-cli",
        f"-datadir={bitcoin_dir}",
        "-rpcuser=doggman",
        "-rpcpassword=donkey",
        "-rpcport=18554",
        "-rpcwallet=test_wallet",
        "-regtest",
    ] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"bitcoin-cli failed: {result.stderr}")
    return result.stdout.strip()


def mine_blocks(count: int, address: str | None = None) -> None:
    """Mine blocks in regtest. If no address, mines to bitcoind's own wallet."""
    if not address:
        address = bitcoin_cli("getnewaddress")
    bitcoin_cli("generatetoaddress", str(count), address)


class LNDTestClient:
    """Async gRPC client for interacting with an LND node during tests.

    This is a simplified version of LNDGrpcClient specifically for testing,
    connecting directly to an LND node (not through the BTCLND daemon).
    """

    def __init__(self, host: str, port: int, lnd_dir: str, network: str = "regtest"):
        self.host = host
        self.port = port
        self.lnd_dir = lnd_dir
        self.network = network
        self.tls_cert_path = os.path.join(lnd_dir, "tls.cert")
        self.macaroon_path = os.path.join(
            lnd_dir, "data", "chain", "bitcoin", network, "admin.macaroon"
        )
        self.channel = None
        self.stub = None

    async def connect(self):
        """Establish the gRPC channel."""
        with open(self.tls_cert_path, "rb") as f:
            cert = f.read()
        ssl_creds = grpc.ssl_channel_credentials(root_certificates=cert)
        macaroon = codecs.encode(open(self.macaroon_path, "rb").read(), "hex").decode()

        def metadata_callback(context, callback):
            callback([("macaroon", macaroon)], None)

        auth_creds = grpc.metadata_call_credentials(metadata_callback)
        combined = grpc.composite_channel_credentials(ssl_creds, auth_creds)
        self.channel = grpc.aio.secure_channel(
            f"{self.host}:{self.port}",
            combined,
            options=[
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )
        self.stub = lightning_pb2_grpc.LightningStub(self.channel)

    async def close(self):
        if self.channel:
            await self.channel.close()

    async def get_info(self):
        return await self.stub.GetInfo(lightning_pb2.GetInfoRequest())

    async def new_address(self) -> str:
        resp = await self.stub.NewAddress(
            lightning_pb2.NewAddressRequest(type=0)
        )
        return resp.address

    async def wallet_balance(self) -> int:
        resp = await self.stub.WalletBalance(lightning_pb2.WalletBalanceRequest())
        return resp.confirmed_balance

    async def channel_balance(self) -> int:
        resp = await self.stub.ChannelBalance(lightning_pb2.ChannelBalanceRequest())
        return resp.local_balance.sat

    async def send_coins(self, addr: str, amount: int, sat_per_vbyte: int = 2) -> str:
        """Send on-chain coins."""
        resp = await self.stub.SendCoins(
            lightning_pb2.SendCoinsRequest(
                addr=addr, amount=amount, sat_per_vbyte=sat_per_vbyte
            )
        )
        return resp.txid

    async def connect_peer(self, pubkey: str, host: str):
        """Connect to a lightning peer."""
        addr = lightning_pb2.LightningAddress(pubkey=pubkey, host=host)
        try:
            await self.stub.ConnectPeer(lightning_pb2.ConnectPeerRequest(addr=addr))
        except grpc.aio.AioRpcError as e:
            if "already connected" not in (e.details() or "").lower():
                raise

    async def open_channel_sync(self, node_pubkey: str, amount: int):
        """Open a channel and return the channel point."""
        resp = await self.stub.OpenChannelSync(
            lightning_pb2.OpenChannelRequest(
                node_pubkey=bytes.fromhex(node_pubkey),
                local_funding_amount=amount,
                push_sat=0,
            )
        )
        return f"{resp.funding_txid_str}:{resp.output_index}"

    async def list_channels(self):
        resp = await self.stub.ListChannels(lightning_pb2.ListChannelsRequest())
        return list(resp.channels)

    async def send_payment_sync(self, payment_request: str):
        """Pay a lightning invoice."""
        resp = await self.stub.SendPaymentSync(
            lightning_pb2.SendRequest(payment_request=payment_request)
        )
        if resp.payment_error:
            raise RuntimeError(f"Payment failed: {resp.payment_error}")
        return resp

    async def decode_pay_req(self, pay_req: str):
        return await self.stub.DecodePayReq(
            lightning_pb2.PayReqString(pay_req=pay_req)
        )

    async def add_invoice(self, value: int, memo: str = "") -> lightning_pb2.AddInvoiceResponse:
        """Create a lightning invoice on this node."""
        return await self.stub.AddInvoice(
            lightning_pb2.Invoice(value=value, memo=memo)
        )

    async def lookup_invoice(self, r_hash: bytes) -> lightning_pb2.Invoice:
        """Look up an invoice by its payment hash."""
        return await self.stub.LookupInvoice(
            lightning_pb2.PaymentHash(r_hash=r_hash)
        )

    async def wait_for_sync(self, timeout: int = 60):
        """Wait for LND to be ready (synced to chain or block_height > 0 in regtest).

        In regtest, synced_to_chain can be False even when LND is functional
        if no new blocks have been mined recently. We check block_height > 0
        as a fallback.
        """
        for _ in range(timeout * 2):
            try:
                info = await self.get_info()
                if info.synced_to_chain or info.block_height > 0:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)
        raise TimeoutError("LND did not sync within timeout")


class BitcartDaemonClient:
    """HTTP client for the BTCLND daemon's JSON-RPC interface."""

    def __init__(self, url: str = "http://localhost:5012", user: str = "electrum", password: str = "electrumz"):
        self.url = url
        self.user = user
        self.password = password
        self._id = 0

    async def call(self, method: str, params: dict | list | None = None) -> dict:
        """Make a JSON-RPC call to the daemon."""
        import aiohttp
        from base64 import b64encode

        self._id += 1
        body = {"method": method, "id": self._id, "params": params or {}}
        auth_str = b64encode(f"{self.user}:{self.password}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=body, headers=headers) as resp:
                data = await resp.json()
                if "error" in data and data["error"]:
                    raise RuntimeError(f"RPC error: {data['error']}")
                return data.get("result")

    async def call_with_wallet(self, method: str, xpub: str, **kwargs) -> dict:
        """Make an RPC call with a wallet (xpub/seed) context."""
        params = {"xpub": xpub}
        params.update(kwargs)
        return await self.call(method, params)


async def fund_customer_wallet(customer: LNDTestClient, amount_btc: float = 10.0):
    """Fund the customer LND wallet by mining blocks to its address.

    In regtest, we need to mine blocks while LND is running so it receives
    ZMQ notifications. We also mine 100+ blocks after the funding block
    to make the coinbase spendable.
    """
    addr = await customer.new_address()
    # Fund via bitcoind sendtoaddress (more reliable than mining to LND address
    # because LND in neutrino mode may not detect coinbase outputs)
    bitcoin_cli("sendtoaddress", addr, "1.0")
    # Mine a block to confirm and make spendable
    mine_blocks(1)
    await asyncio.sleep(1)
    # Mine more blocks so LND processes them
    mine_blocks(5)
    # Wait for LND to process the blocks
    for _ in range(30):
        balance = await customer.wallet_balance()
        if balance > 0:
            return balance
        await asyncio.sleep(1)
    balance = await customer.wallet_balance()
    assert balance > 0, f"Customer wallet not funded, balance={balance}"
    return balance


async def setup_lightning_channel(
    customer: LNDTestClient,
    merchant: LNDTestClient,
    merchant_p2p_port: int,
    channel_size: int = 1_000_000,
):
    """Open a lightning channel from customer to merchant.

    Returns the channel point string.
    """
    # Get merchant's node info
    merchant_info = await merchant.get_info()
    merchant_pubkey = merchant_info.identity_pubkey

    # Connect peers
    await customer.connect_peer(merchant_pubkey, f"127.0.0.1:{merchant_p2p_port}")

    # Open channel
    channel_point = await customer.open_channel_sync(merchant_pubkey, channel_size)

    # Mine blocks to confirm the channel
    mine_blocks(6)
    await asyncio.sleep(2)  # let both nodes process the blocks
    await customer.wait_for_sync()
    await merchant.wait_for_sync()

    # Wait for channel to be active
    for _ in range(30):
        channels = await customer.list_channels()
        if any(ch.active for ch in channels):
            return channel_point
        await asyncio.sleep(1)

    raise TimeoutError("Channel did not become active")
