from base import BaseDaemon  # isort: skip

import os
import secrets
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from logger import get_logger
from storage import Storage, decimal_to_string
from utils import AbstractRPCProvider, MultipleProviderRPC, exception_retry_middleware, load_json_dict, rpc

from genericprocessor import (
    BlockchainFeatures,
    BlockProcessorDaemon,
    Invoice as BaseInvoice,
    KeyStore as BaseKeyStore,
    Transaction as BaseTransaction,
    Wallet as BaseWallet,
    WalletDB,
    from_wei,
    str_to_bool,
    NOOP_PATH,
)

logger = get_logger(__name__)

DIVISIBILITY = 6  # 1 XRP = 1,000,000 drops
MAX_DESTINATION_TAG = 2**32 - 1


# ─── Multi-server RPC provider ───────────────────────────────────────────────


class XRPLRPCProvider(AbstractRPCProvider):
    """Thin wrapper around xrpl AsyncJsonRpcClient compatible with MultipleProviderRPC."""

    def __init__(self, url):
        from xrpl.asyncio.clients import AsyncJsonRpcClient

        self.endpoint_uri = url
        self.client = AsyncJsonRpcClient(url)

    async def send_single_request(self, request_obj, **kwargs):
        response = await self.client.request(request_obj)
        return response

    async def send_ping_request(self):
        from xrpl.models.requests import ServerInfo

        await self.client.request(ServerInfo())


class MultipleRPCXRPLProvider:
    """Failover provider wrapping MultipleProviderRPC for xrpl-py request objects."""

    def __init__(self, rpc):
        self.rpc = rpc

    async def request(self, request_obj):
        return await self.rpc.send_request(request_obj)

    @property
    def endpoint_uri(self):
        return self.rpc.current_rpc.endpoint_uri


# ─── BlockchainFeatures ──────────────────────────────────────────────────────


class XRPFeatures(BlockchainFeatures):
    def __init__(self, provider):
        self.provider = provider

    async def _request(self, request_obj):
        response = await self.provider.request(request_obj)
        if not response.is_successful():
            error = response.result.get("error_message", response.result.get("error", "Unknown XRP error"))
            raise Exception(f"XRP RPC error: {error}")
        return response

    async def get_block_number(self):
        from xrpl.models.requests import Ledger

        response = await self._request(Ledger(ledger_index="validated"))
        return response.result["ledger_index"]

    async def is_connected(self):
        try:
            await self.get_block_number()
            return True
        except Exception:
            return False

    async def get_gas_price(self):
        from xrpl.models.requests import Fee

        response = await self._request(Fee())
        return int(response.result.get("drops", {}).get("open_ledger_fee", "12"))

    async def get_transaction(self, tx):
        from xrpl.models.requests import Tx

        response = await self._request(Tx(transaction=tx))
        return response.result

    async def get_tx_receipt(self, tx):
        return await self.get_transaction(tx)

    async def get_balance(self, address):
        from xrpl.models.requests import AccountInfo

        try:
            response = await self._request(
                AccountInfo(account=address, ledger_index="validated", strict=True)
            )
            return Decimal(response.result["account_data"]["Balance"])
        except Exception:
            return Decimal(0)

    async def get_block(self, block, *args, **kwargs):
        from xrpl.models.requests import Ledger

        if block == "latest":
            block = "validated"
        ledger_index = block if isinstance(block, str) else int(block)
        response = await self._request(Ledger(ledger_index=ledger_index, transactions=False))
        return response.result.get("ledger", {})

    async def get_block_txes(self, block):
        from xrpl.models.requests import Ledger

        response = await self._request(
            Ledger(ledger_index=int(block), transactions=True, expand=True)
        )
        return response.result.get("ledger", {}).get("transactions", [])

    async def chain_id(self):
        return 0  # XRP Ledger does not use chain IDs

    def is_address(self, address):
        from xrpl.core.addresscodec import is_valid_classic_address, is_valid_xaddress

        return is_valid_classic_address(address) or is_valid_xaddress(address)

    def normalize_address(self, address):
        from xrpl.core.addresscodec import is_valid_xaddress, xaddress_to_classic_address

        if is_valid_xaddress(address):
            classic, _, _ = xaddress_to_classic_address(address)
            return classic
        return address

    async def get_payment_uri(self, address, amount, divisibility, contract=None, destination_tag=None):
        amount_drops = int(Decimal(str(amount)) * Decimal(10**divisibility))
        uri = f"xrpl:{address}?amount={amount_drops}"
        if destination_tag is not None:
            uri += f"&dt={destination_tag}"
        return uri

    async def process_tx_data(self, data):
        # xrpl-py 4.x wraps tx fields under "tx_json" in both Tx and Ledger responses
        tx = data.get("tx_json", data)
        meta = data.get("metaData") or data.get("meta") or {}
        if tx.get("TransactionType") != "Payment":
            return None
        result = meta.get("TransactionResult", "")
        if result != "tesSUCCESS":
            return None
        # Always use delivered_amount for actual amount (handles partial payments)
        # xrpl-py 4.x uses "DeliverMax" instead of "Amount"
        delivered = meta.get("delivered_amount", tx.get("DeliverMax", tx.get("Amount")))
        if isinstance(delivered, dict):
            # Issued currency (trust line token) — skip for native XRP support
            return None
        return Transaction(
            hash=data.get("hash", ""),
            from_addr=tx.get("Account", ""),
            to=self.normalize_address(tx.get("Destination", "")),
            value=int(delivered),
            destination_tag=tx.get("DestinationTag"),
        )

    def get_tx_hash(self, tx_data):
        return tx_data.get("hash", tx_data.get("tx_json", {}).get("hash", ""))

    async def get_confirmations(self, tx_hash, data=None):
        if data is None:
            data = await self.get_transaction(tx_hash)
        if not data.get("validated", False):
            return 0
        tx_ledger = data.get("ledger_index", 0)
        current = await self.get_block_number()
        return max(0, current - tx_ledger + 1)

    def current_server(self):
        return self.provider.endpoint_uri


# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class Transaction(BaseTransaction):
    destination_tag: int = None


@dataclass
class Invoice(BaseInvoice):
    destination_tag: int = 0


# ─── KeyStore ─────────────────────────────────────────────────────────────────


@dataclass
class KeyStore(BaseKeyStore):
    def load_account_from_key(self):
        from xrpl.core.addresscodec import is_valid_classic_address, is_valid_xaddress, xaddress_to_classic_address
        from xrpl.core.keypairs import derive_classic_address, derive_keypair

        key = self.key
        # Try as XRP seed (sXXX... format or RFC-1751 mnemonic)
        try:
            pub, priv = derive_keypair(key)
            self.public_key = pub
            self.private_key = priv
            self.address = derive_classic_address(pub)
            self.seed = key
            return
        except Exception:
            pass
        # Try as classic address (watching-only)
        if is_valid_classic_address(key):
            self.address = key
            return
        # Try as X-address (watching-only, extract classic address)
        if is_valid_xaddress(key):
            classic, _, _ = xaddress_to_classic_address(key)
            self.address = classic
            return
        raise Exception("Invalid XRP key: must be a seed (sXXX...), classic address (rXXX...), or X-address")

    def add_privkey(self, privkey):
        from xrpl.core.keypairs import derive_classic_address, derive_keypair

        try:
            pub, priv = derive_keypair(privkey)
        except Exception as e:
            raise Exception("Invalid XRP seed provided") from e
        address = derive_classic_address(pub)
        if address != self.address:
            raise Exception("Invalid seed imported: address mismatch")
        self.seed = privkey
        self.public_key = pub
        self.private_key = priv


# ─── Wallet ───────────────────────────────────────────────────────────────────


class Wallet(BaseWallet):
    """XRP wallet using destination tags to identify payments."""

    def generate_destination_tag(self):
        """Generate a unique uint32 destination tag for a new invoice."""
        while True:
            tag = secrets.randbelow(MAX_DESTINATION_TAG) + 1  # 1..4294967295
            if str(tag) not in self.request_addresses:
                return tag

    async def create_payment_request_object(self, address, amount, message, expiration, timestamp):
        dest_tag = self.generate_destination_tag()
        return Invoice(
            address=address,
            message=message,
            time=timestamp,
            amount=amount,
            sent_amount=Decimal(0),
            exp=expiration,
            id=secrets.token_urlsafe(),
            height=await self.coin.get_block_number(),
            destination_tag=dest_tag,
            payment_address=str(dest_tag),
        )

    def add_payment_request(self, req, save_db=True):
        self.receive_requests[req.id] = req
        if req.payment_address:
            self.request_addresses[req.payment_address] = req.id
        if save_db:
            self.save_db()
        return req

    async def export_request(self, req):
        d = await super().export_request(req)
        dest_tag = getattr(req, "destination_tag", None)
        if dest_tag is not None:
            d["destination_tag"] = dest_tag
            # Override URI to include destination tag and use wallet address (not tag string)
            d["URI"] = await self.coin.get_payment_uri(
                self.address, req.amount, self.divisibility, destination_tag=dest_tag
            )
        return d


# ─── XRP Daemon ───────────────────────────────────────────────────────────────


class XRPDaemon(BlockProcessorDaemon):
    name = "XRP"
    BASE_SPEC_FILE = "daemons/spec/xrp.json"
    DEFAULT_PORT = 5012

    DIVISIBILITY = DIVISIBILITY
    AMOUNTGEN_DIVISIBILITY = 6
    BLOCK_TIME = 4  # XRP ledgers close every 3-5 seconds
    DEFAULT_MAX_SYNC_BLOCKS = 300  # ~20 minutes of ledger history

    UNIT = "drop"

    KEYSTORE_CLASS = KeyStore
    WALLET_CLASS = Wallet
    INVOICE_CLASS = Invoice

    ARCHIVE_SUPPORTED = False

    def get_default_server_url(self):
        return "https://xrplcluster.com"

    async def create_coin(self, archive=False):
        server_list = self.SERVER[:]
        providers = []
        for server in server_list:
            provider = XRPLRPCProvider(server)
            provider.send_single_request = exception_retry_middleware(
                provider.send_single_request, (Exception,)
            )
            providers.append(provider)
        multi = MultipleProviderRPC(providers)
        await multi.start()
        self.coin = XRPFeatures(MultipleRPCXRPLProvider(multi))
        self.coin.get_block_safe = self.coin.get_block

    async def shutdown_coin(self, final=False, archive_only=False):
        if hasattr(self, "coin") and self.coin:
            await self.coin.provider.rpc.stop()

    # ── Payment detection using destination tags ──

    async def process_transaction(self, tx):
        """Override: match payments by destination tag instead of sender address."""
        if tx.divisibility is None:
            tx.divisibility = self.DIVISIBILITY
        to = tx.to
        amount = from_wei(tx.value, tx.divisibility)
        if to not in self.addresses:
            return
        for wallet_key in self.addresses[to]:
            await self.trigger_event(
                {
                    "event": "new_transaction",
                    "tx": tx.hash,
                    "from_address": tx.from_addr,
                    "to": tx.to,
                    "amount": decimal_to_string(amount, tx.divisibility),
                    "destination_tag": tx.destination_tag,
                },
                wallet_key,
            )
            # Match by destination tag (not sender address like ETH/TRX)
            if tx.destination_tag is not None:
                tag_key = str(tx.destination_tag)
                if tag_key in self.wallets[wallet_key].request_addresses:
                    self.loop.create_task(
                        self.wallets[wallet_key].process_new_payment(tag_key, tx, amount, wallet_key)
                    )

    # ── Wallet loading ──

    async def load_wallet(self, xpub, contract, diskless=False, extra_params=None):
        if extra_params is None:
            extra_params = {}
        wallet_key = self.coin.get_wallet_key(xpub)
        if wallet_key in self.wallets:
            return self.wallets[wallet_key]
        if not xpub:
            return None
        if diskless:
            wallet = self.restore_wallet_from_text(xpub, path=NOOP_PATH)
        else:
            wallet_dir = self.get_wallet_path()
            wallet_path = os.path.join(wallet_dir, wallet_key)
            if not os.path.exists(wallet_path):
                self.restore(xpub, wallet_path=wallet_path)
            storage = Storage(wallet_path)
            db = WalletDB(storage.read())
            wallet = self.WALLET_CLASS(self.coin, db, storage)
        self.wallets[wallet_key] = wallet
        self.wallets_updates[wallet_key] = deque(maxlen=self.POLLING_CAP)
        self.addresses[wallet.address].add(wallet_key)
        await wallet.start(self.latest_blocks.copy())
        return wallet

    # ── RPC Methods ──

    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        raise NotImplementedError("Not supported for XRP")

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        from xrpl.models.requests import SubmitOnly

        blob = tx if isinstance(tx, str) else load_json_dict(tx, "Invalid transaction").get("tx_blob", tx)
        response = await self.coin._request(SubmitOnly(tx_blob=blob))
        return self.coin.to_dict(response.result)

    @rpc(requires_network=True)
    async def get_default_fee(self, tx, wallet=None):
        fee_drops = await self.coin.get_gas_price()
        return self.coin.to_dict(from_wei(fee_drops, DIVISIBILITY))

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        data = load_json_dict(tx_data, "Invalid transaction")
        return data.get("hash", data.get("tx_hash", ""))

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        raise NotImplementedError("Transaction size estimation not supported for XRP")

    @rpc(requires_network=True)
    async def get_used_fee(self, tx_hash, wallet=None):
        data = await self.coin.get_transaction(tx_hash)
        tx_json = data.get("tx_json", data)
        fee_drops = int(tx_json.get("Fee", "0"))
        return self.coin.to_dict(from_wei(fee_drops, DIVISIBILITY))

    @rpc(requires_network=True)
    async def gettransaction(self, tx, wallet=None):
        data = await self.coin.get_transaction(tx)
        # xrpl-py 4.x nests tx fields under tx_json
        tx_json = data.get("tx_json", data)
        meta = data.get("meta", {})
        result = {
            "tx_hash": data.get("hash", ""),
            "from_address": tx_json.get("Account", ""),
            "to_address": tx_json.get("Destination", ""),
            "amount": tx_json.get("DeliverMax", tx_json.get("Amount", "0")),
            "fee": tx_json.get("Fee", "0"),
            "destination_tag": tx_json.get("DestinationTag"),
            "ledger_index": data.get("ledger_index"),
            "validated": data.get("validated", False),
            "confirmations": await self.coin.get_confirmations(tx, data),
        }
        if meta:
            result["delivered_amount"] = meta.get("delivered_amount")
            result["transaction_result"] = meta.get("TransactionResult")
        return self.coin.to_dict(result)

    @rpc(requires_wallet=True)
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        unused, funded, balance = str_to_bool(unused), str_to_bool(funded), str_to_bool(balance)
        address = self.wallets[wallet].address
        addr_balance = await self.coin.get_balance(address)
        if (unused and addr_balance > 0) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, self.coin.to_dict(addr_balance))]
        return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", full_info=False, wallet=None):
        from xrpl.core.keypairs import generate_seed

        seed = generate_seed()
        if full_info:
            keystore = self.KEYSTORE_CLASS(key=seed)
            return {
                "seed": seed,
                "address": keystore.address,
                "public_key": keystore.public_key,
            }
        return seed

    @rpc(requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        from xrpl.core.addresscodec import is_valid_xaddress, xaddress_to_classic_address
        from xrpl.models.requests import AccountInfo
        from xrpl.models.transactions import Payment
        from xrpl.utils import xrp_to_drops

        address = self.wallets[wallet].address

        # Handle X-address (may contain embedded destination tag)
        dest_tag = kwargs.get("destination_tag")
        if is_valid_xaddress(destination):
            classic, tag, _ = xaddress_to_classic_address(destination)
            destination = classic
            if tag is not None:
                dest_tag = tag

        amount_drops = xrp_to_drops(Decimal(str(amount)))

        # Build payment
        payment_fields = {
            "account": address,
            "destination": destination,
            "amount": amount_drops,
        }
        if dest_tag is not None:
            payment_fields["destination_tag"] = int(dest_tag)
        if fee:
            payment_fields["fee"] = xrp_to_drops(Decimal(str(fee)))

        payment = Payment(**payment_fields)

        if unsigned:
            return self.coin.to_dict(payment.to_dict())

        private_key = self.wallets[wallet].get_private_key()

        # Autofill sequence, fee, last_ledger_sequence then sign
        from xrpl.asyncio.transaction import autofill, sign as xrpl_sign
        from xrpl.wallet import Wallet as XRPLWallet

        client = self.coin.provider.rpc.current_rpc.client
        prepared = await autofill(payment, client)
        xrpl_wallet = XRPLWallet(
            public_key=self.wallets[wallet].keystore.public_key,
            private_key=private_key,
        )
        signed = xrpl_sign(prepared, xrpl_wallet)

        # Submit the signed tx blob
        from xrpl.models.requests import SubmitOnly

        response = await self.coin._request(SubmitOnly(tx_blob=signed.blob()))
        return self.coin.to_dict(response.result)

    @rpc(requires_wallet=True)
    def signmessage(self, address=None, message=None, wallet=None):
        raise NotImplementedError("Message signing not yet supported for XRP")

    def _sign_transaction(self, tx, private_key):
        from xrpl.core.keypairs import derive_keypair
        from xrpl.models.transactions import Payment
        from xrpl.transaction import sign as xrpl_sign
        from xrpl.wallet import Wallet as XRPLWallet

        if isinstance(tx, str):
            tx = load_json_dict(tx, "Invalid transaction")
        # The keystore stores the seed, derive keypair from it
        # XRPLWallet expects hex private key, not the seed
        pub, priv = derive_keypair(private_key)
        xrpl_wallet = XRPLWallet(public_key=pub, private_key=priv)
        tx_obj = Payment.from_xrpl(tx)
        signed = xrpl_sign(tx_obj, xrpl_wallet)
        return signed.blob()

    @rpc
    def validatecontract(self, address, wallet=None):
        return False  # XRP doesn't use smart contracts

    @rpc
    def get_tokens(self, wallet=None):
        return {}  # Trust line tokens not yet supported

    @rpc
    def getabi(self, wallet=None):
        return []  # No ABI concept in XRP


daemon = XRPDaemon()
daemon.start()
