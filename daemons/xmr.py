import asyncio
import binascii
import json
import os
import secrets
import traceback
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from aiohttp import ClientError as AsyncClientError
from genericprocessor import NOOP_PATH, PR_PAID, PR_UNCONFIRMED, PR_UNPAID, BlockchainFeatures, BlockProcessorDaemon
from genericprocessor import Invoice as BaseInvoice
from genericprocessor import KeyStore as BaseKeyStore
from genericprocessor import Transaction as BaseTransaction
from genericprocessor import Wallet as BaseWallet
from genericprocessor import WalletDB, daemon_ctx, decimal_to_string, from_wei, str_to_bool
from jsonrpc import RPCProvider
from monero import const as monero_const
from monero import ed25519
from monero.address import address as address_func
from monero.backends.offline import OfflineWallet
from monero.keccak import keccak_256
from monero.numbers import from_atomic
from monero.seed import Seed
from monero.transaction import ExtraParser
from monero.transaction import Transaction as MoneroTransaction
from monero.wallet import Wallet as MoneroWallet
from storage import JSONEncoder as StorageJSONEncoder
from storage import Storage
from utils import exception_retry_middleware, load_json_dict, rpc

MAX_FETCH_TXES = 100


def is_valid_hash(hexhash):
    try:
        bytearray.fromhex(hexhash)
        return len(hexhash) == 64
    except ValueError:
        return


class JSONEncoder(StorageJSONEncoder):
    def default(self, obj):
        if isinstance(obj, MoneroTransaction):
            return obj.__dict__
        return super().default(obj)


@dataclass
class Transaction(BaseTransaction):
    monero_tx: MoneroTransaction = None


class MoneroRPC(RPCProvider):
    def __init__(self, url):
        super().__init__(url)
        self.jsonrpc_request = exception_retry_middleware(
            self.jsonrpc_request, (AsyncClientError, TimeoutError, asyncio.TimeoutError), daemon_ctx.get().VERBOSE
        )
        self.raw_request = exception_retry_middleware(
            self.raw_request, (AsyncClientError, TimeoutError, asyncio.TimeoutError), daemon_ctx.get().VERBOSE
        )

    @staticmethod
    def _validate_hashes(hashes):
        if any(map(lambda h: not is_valid_hash(h), hashes)):
            raise Exception("Invalid tx hash")

    async def get_transactions(self, hashes):
        self._validate_hashes(hashes)
        results = []
        for start_idx in range(0, len(hashes), MAX_FETCH_TXES):
            results.extend(await self._fetch_tx_list(hashes[start_idx : start_idx + MAX_FETCH_TXES]))
        return results

    async def _fetch_tx_list(self, hashes):
        resp = await self.raw_request(
            "get_transactions",
            txs_hashes=hashes,
            decode_as_json=True,
        )
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        txs = []
        for tx in resp.get("txs", []):
            as_json = json.loads(tx["as_json"])
            fee = as_json.get("rct_signatures", {}).get("txnFee")
            txs.append(
                MoneroTransaction(
                    hash=tx["tx_hash"],
                    fee=from_atomic(fee) if fee else None,
                    height=None if tx["in_pool"] else tx["block_height"],
                    timestamp=datetime.fromtimestamp(tx["block_timestamp"]) if "block_timestamp" in tx else None,
                    output_indices=tx["output_indices"] if "output_indices" in tx else None,
                    blob=binascii.unhexlify(tx["as_hex"]) or None,
                    json=as_json,
                )
            )
        return txs

    async def get_block(self, height):
        resp = await self.jsonrpc_request("get_block", height=height)
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        block = resp["block_header"]
        json_part = json.loads(resp["json"])
        return {
            **json_part,
            **block,
            "transactions": await self.get_transactions([block["miner_tx_hash"]] + json_part["tx_hashes"]),
        }

    async def get_mempool(self):
        resp = await self.raw_request("get_transaction_pool")
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        return resp.get("transactions", [])

    async def broadcast(self, tx):
        resp = await self.raw_request("send_raw_transaction", tx_as_hex=tx)
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        return resp

    async def get_fee_estimate(self):
        resp = await self.jsonrpc_request("get_fee_estimate")
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        return resp["fee"]


class XMRFeatures(BlockchainFeatures):
    rpc: MoneroRPC

    def __init__(self, rpc):
        self.rpc = rpc
        self.get_block_safe = self.get_block
        self.get_tx_receipt_safe = self.get_tx_receipt

    async def get_block_number(self):
        return (await self.rpc.jsonrpc_request("get_block_count"))["count"] - 1

    async def is_connected(self):
        return True

    async def get_gas_price(self):
        return await self.rpc.get_fee_estimate()

    async def is_syncing(self):
        return False

    async def get_transaction(self, tx):
        data = await self.rpc.get_transactions([tx])
        if not data:
            raise Exception("Transaction not found")
        return data[0]

    get_tx_receipt = get_transaction

    async def get_balance(self, address):
        # TODO: implement somehow
        return Decimal(0)

    async def get_block(self, block, *args, **kwargs):
        return await self.rpc.get_block(block)

    async def get_block_txes(self, block):
        return (await self.get_block_safe(block))["transactions"]

    async def chain_id(self):
        return 1

    def is_address(self, address):
        try:
            address_func(address)
            return True
        except ValueError:
            return False

    def normalize_address(self, address):
        return address

    async def get_peer_list(self):
        return []

    async def get_payment_uri(self, req, divisibility, contract=None):
        return f"monero:{req.address}?tx_amount={decimal_to_string(req.amount, XMRDaemon.DIVISIBILITY)}"

    async def process_tx_data(self, data):
        return Transaction(
            data.hash,
            None,
            None,
            None,
            monero_tx=data,
        )

    def get_tx_hash(self, tx_data):
        return tx_data.hash

    def get_wallet_key(self, xpub, *args, **kwargs):
        return xpub

    async def get_confirmations(self, tx_hash, data=None) -> int:
        data = data or await self.get_tx_receipt_safe(tx_hash)
        current_height = await self.get_block_number()
        return max(0, current_height - (data.height or current_height + 1) + 1)

    def to_dict(self, obj):
        return json.loads(JSONEncoder(precision=daemon_ctx.get().DIVISIBILITY).encode(obj))


class KeyStore(BaseKeyStore):
    address: str = None

    def load_account_from_key(self):
        try:
            self.add_privkey(self.key, check_address=False)
        except Exception:
            address = address_func(self.address)
            if ed25519.public_from_secret_hex(self.key) == address.view_key():
                self.public_key = self.key
        if self.address is None:
            raise Exception("Address not provided or can't be derived")
        if self.public_key is None:
            raise Exception("Missing secret viewkey required for payments detection")

    def add_privkey(self, privkey, check_address=True):
        try:
            if len(privkey.split(" ")) == 1 and len(privkey) % 8 == 0:
                raise Exception("Hexadecimal seed not supported")
            seed = Seed(privkey)
            private_key = seed.secret_spend_key()
            public_key = seed.secret_view_key()
            address = str(seed.public_address(net=daemon_ctx.get().network_const))
        except Exception:
            raise Exception("Invalid seed provided")
        if check_address and address != self.address:
            raise Exception("Invalid seed imported: address mismatch")
        self.seed = privkey
        self.private_key = private_key
        self.public_key = public_key
        self.address = address

    @classmethod
    def load(cls, db):
        return cls(key=db.get("key", ""), address=db.get("address", ""))

    def dump(self):
        return {"key": self.key, "address": self.address}


@dataclass
class Invoice(BaseInvoice):
    confirmed_amount: Decimal = Decimal(0)

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.confirmed_amount, str):
            self.confirmed_amount = Decimal(self.confirmed_amount)


@dataclass
class Wallet(BaseWallet):
    def add_payment_request(self, req, save_db=True):
        self.receive_requests[req.id] = req
        self.request_addresses[req.address] = req.id
        if save_db:
            self.save_db()
        return req

    def remove_from_detection_dict(self, req):
        self.request_addresses.pop(req.address, None)

    async def create_payment_request_object(self, address, amount, message, expiration, timestamp):
        invoice_id = secrets.token_hex(8)
        return Invoice(
            address=str(address_func(address).with_payment_id(invoice_id)),
            message=message,
            time=timestamp,
            amount=amount,
            sent_amount=Decimal(0),
            exp=expiration,
            id=invoice_id,
            height=await self.coin.get_block_number(),
        )

    async def process_new_payment(self, to_address, tx, payment, wallet, unconfirmed=False):
        req = self.get_request(to_address)
        if req is None or req.status not in (PR_UNPAID, PR_UNCONFIRMED):
            return
        if unconfirmed:
            req.sent_amount += payment.amount
        else:
            req.confirmed_amount += payment.amount
        req.sent_amount = max(req.sent_amount, req.confirmed_amount)
        if (unconfirmed and req.sent_amount >= req.amount) or req.confirmed_amount >= req.amount:
            await self.process_payment(wallet, req.id, tx_hash=tx.hash, status=PR_UNCONFIRMED if unconfirmed else PR_PAID)
        else:
            self.save_db()


class XMRDaemon(BlockProcessorDaemon):
    name = "XMR"
    BASE_SPEC_FILE = "daemons/spec/eth.json"
    DEFAULT_PORT = 5011

    DIVISIBILITY = 12
    BLOCK_TIME = 60
    MEMPOOL_TIME = 5

    DEFAULT_MAX_SYNC_BLOCKS = 300  # 10 hours
    # from coingecko API
    FIAT_NAME = "monero"

    UNIT = "piconero"

    KEYSTORE_CLASS = KeyStore
    WALLET_CLASS = Wallet
    INVOICE_CLASS = Invoice

    NETWORK_MAPPING = {"mainnet": monero_const.NET_MAIN, "testnet": monero_const.NET_TEST, "stagenet": monero_const.NET_STAGE}

    def __init__(self):
        super().__init__()
        self.network_const = self.NETWORK_MAPPING.get(self.NET.lower())
        self.mempool_cache = {}
        if not self.network_const:
            raise ValueError(
                f"Invalid network passed: {self.NET}. Valid choices are {', '.join(self.NETWORK_MAPPING.keys())}."
            )

    async def on_startup(self, app):
        await super().on_startup(app)
        self.loop.create_task(self.process_mempool())

    def create_mempool_tx(self, tx):
        as_json = json.loads(tx["tx_json"])
        fee = as_json.get("rct_signatures", {}).get("txnFee")
        return MoneroTransaction(
            hash=tx["id_hash"],
            fee=from_atomic(fee) if fee else None,
            height=None,
            timestamp=None,
            output_indices=None,
            blob=binascii.unhexlify(tx["tx_blob"]) or None,
            json=as_json,
        )

    async def process_mempool(self):  # noqa: C901
        while self.running:
            try:
                mempool = await self.coin.rpc.get_mempool()
                new_cache = {}
                for tx_data in mempool:
                    try:
                        tx = await self.coin.process_tx_data(self.create_mempool_tx(tx_data))
                        if tx is not None:
                            if tx.hash in self.mempool_cache:
                                continue
                            new_cache[tx.hash] = True
                            await self.process_transaction(tx, unconfirmed=True)
                    except Exception:
                        if self.VERBOSE:
                            print(f"Error processing transaction {self.coin.get_tx_hash(tx_data)}:")
                            print(traceback.format_exc())
                self.mempool_cache = new_cache
            except Exception:
                if self.VERBOSE:
                    print("Error processing mempool:")
                    print(traceback.format_exc())
            await asyncio.sleep(self.MEMPOOL_TIME)

    def create_coin(self):
        self.coin = XMRFeatures(MoneroRPC(self.SERVER))

    def get_default_server_url(self):
        return ""

    async def load_wallet(self, xpub, contract, diskless=False, extra_params={}):
        address = extra_params.get("address", None)
        wallet_key = self.coin.get_wallet_key(xpub)
        if wallet_key in self.wallets:
            return self.wallets[wallet_key]
        if not xpub:
            return None

        if diskless:
            wallet = self.restore_wallet_from_text(xpub, path=NOOP_PATH, address=address)
        else:
            wallet_dir = self.get_wallet_path()
            wallet_path = os.path.join(wallet_dir, wallet_key)
            if not os.path.exists(wallet_path):
                self.restore(xpub, wallet_path=wallet_path, address=address)
            storage = Storage(wallet_path)
            db = WalletDB(storage.read())
            wallet = Wallet(self.coin, db, storage)
        self.wallets[wallet_key] = wallet
        self.wallets_updates[wallet_key] = []
        self.addresses[wallet.address].add(wallet_key)
        await wallet.start(self.latest_blocks.copy())
        return wallet

    def get_final_tx_address(self, address, tx, wallet):
        ep = ExtraParser(tx.monero_tx.json["extra"])
        d = ep.parse()
        svk = binascii.unhexlify(wallet.view_key())
        encrypted_payment_id = d["nonces"][0][1:]
        svk_2 = ed25519.scalar_add(svk, svk)
        svk_4 = ed25519.scalar_add(svk_2, svk_2)
        svk_8 = ed25519.scalar_add(svk_4, svk_4)
        shared_secret = bytearray(ed25519.scalarmult(svk_8, tx.monero_tx.pubkeys[0]))
        shared_secret.append(0x8D)
        shared_secret = keccak_256(shared_secret).digest()
        payment_id = bytearray(encrypted_payment_id)
        for i in range(len(payment_id)):
            payment_id[i] ^= shared_secret[i]
        return address_func(address).with_payment_id(binascii.hexlify(payment_id).decode())

    async def process_transaction(self, tx, unconfirmed=False):  # noqa: C901
        if tx.divisibility is None:
            tx.divisibility = self.DIVISIBILITY
        current_height = await self.coin.get_block_number()
        # NOTE: do not process locked funds
        if current_height <= tx.monero_tx.json["unlock_time"]:
            return
        for address in self.addresses:
            try:
                first_wallet = self.wallets[next(iter(self.addresses[address]))]
            except StopIteration:
                continue
            w = MoneroWallet(
                OfflineWallet(
                    address,
                    view_key=first_wallet.keystore.public_key,
                )
            )
            try:
                for output in tx.monero_tx.outputs(wallet=w):
                    if output.payment is not None:
                        final_address = self.get_final_tx_address(address, tx, w)
                        for wallet in self.addresses[address]:
                            await self.trigger_event({"event": "new_transaction", "tx": tx.hash}, wallet)
                            if final_address in self.wallets[wallet].request_addresses:
                                await self.wallets[wallet].process_new_payment(
                                    final_address, tx, output.payment, wallet, unconfirmed=unconfirmed
                                )
            except Exception:
                if self.VERBOSE:
                    print(f"Error processing transaction {tx.hash}:")
                    print(traceback.format_exc())

    ### Methods ###
    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        raise NotImplementedError("Not supported in monero")

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        return self.coin.to_dict(await self.coin.rpc.broadcast(tx))

    @rpc(requires_network=True)
    async def get_default_fee(self, tx, wallet=None):
        raise NotImplementedError("Currently not supported")

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        return load_json_dict(tx_data, "Invalid transaction")["tx_hash"]

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        raise NotImplementedError("Currently not supported")

    @rpc(requires_network=True)
    async def get_used_fee(self, tx_hash, wallet=None):
        tx_stats = await self.get_tx_status(tx_hash)
        return self.coin.to_dict(tx_stats["gasUsed"] * from_wei(tx_stats["effectiveGasPrice"]))

    @rpc(requires_network=True)
    async def gettransaction(self, tx, wallet=None):
        tx_obj = await self.coin.get_transaction(tx)
        data = {
            **tx_obj.json,
            "fee": tx_obj.fee,
            "tx_hash": tx_obj.hash,
            "height": tx_obj.height,
            "confirmations": await self.coin.get_confirmations(tx, tx_obj),
        }
        return self.coin.to_dict(data)

    @rpc(requires_network=True)
    async def get_tx_status(self, tx, wallet=None):
        return await self.gettransaction(tx)

    @rpc(requires_wallet=True)
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        unused, funded, balance = str_to_bool(unused), str_to_bool(funded), str_to_bool(balance)
        address = self.wallets[wallet].address
        addr_balance = await self.coin.get_balance(address)
        if (unused and (addr_balance > 0)) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, self.coin.to_dict(addr_balance))]
        else:
            return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", wallet=None):
        return Seed().phrase

    @rpc(requires_wallet=True, requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        raise NotImplementedError("Currently not supported")

    @rpc(requires_wallet=True)
    def signmessage(self, address=None, message=None, wallet=None):
        raise NotImplementedError("Currently not supported")

    def _sign_transaction(self, tx, private_key):
        raise NotImplementedError("Currently not supported")

    @rpc
    def verifymessage(self, address, signature, message, wallet=None):
        raise NotImplementedError("Currently not supported")

    @rpc
    def validatekey(self, key, address=None, wallet=None):
        try:
            daemon_ctx.get().KEYSTORE_CLASS(key, address=address)
            return True
        except Exception:
            return False

    @rpc(requires_wallet=True)  # fallback
    def setrequestaddress(self, key, address, wallet):
        return False


if __name__ == "__main__":
    daemon = XMRDaemon()
    daemon.start()
