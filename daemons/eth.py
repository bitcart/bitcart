import asyncio
import functools
import inspect
import json
import os
import random
import secrets
import time
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from typing import ClassVar

from base import BaseDaemon
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import PrivateKey, PublicKey
from hexbytes import HexBytes
from mnemonic import Mnemonic
from storage import JSONEncoder as StorageJSONEncoder
from storage import Storage, StoredObject
from storage import WalletDB as StorageWalletDB
from utils import JsonResponse, get_exception_message, hide_logging_errors, rpc
from web3 import Web3
from web3.datastructures import AttributeDict
from web3.eth import AsyncEth
from web3.geth import AsyncGethAdmin, Geth
from web3.providers.rpc import get_default_http_endpoint

Account.enable_unaudited_hdwallet_features()

NO_HISTORY_MESSAGE = "We don't access transaction history to remain lightweight"
WRITE_DOWN_SEED_MESSAGE = "Please keep your seed in a safe place; if you lose it, you will not be able to restore your wallet."
ONE_ADDRESS_MESSAGE = "We only support one address per wallet as it is common in ethereum ecosystem"
GET_PROOF_MESSAGE = "Geth doesn't support get_proof correctly for now"
NO_MASTER_KEYS_MESSAGE = "As we use only one address per wallet, address keys are used, but not the xprv/xpub"

CHUNK_SIZE = 30
AMOUNTGEN_PRECISION = Decimal(10) ** (-18)
AMOUNTGEN_LIMIT = 10**9
# TODO: limit sync post-reboot to (60/12)*60=5*60=300 blocks (max expiry time)

# statuses of payment requests
PR_UNPAID = 0  # invoice amt not reached by txs in mempool+chain.
PR_EXPIRED = 1  # invoice is unpaid and expiry time reached
PR_PAID = 3  # paid and mined (1 conf).


pr_tooltips = {
    PR_UNPAID: "Unpaid",
    PR_PAID: "Paid",
    PR_EXPIRED: "Expired",
}


STR_TO_BOOL_MAPPING = {
    "true": True,
    "yes": True,
    "1": True,
    "false": False,
    "no": False,
    "0": False,
}  # common str -> bool conversions

# storage


class WalletDB(StorageWalletDB):
    WALLET_VERSION = 1

    def _convert_dict(self, path, key, v):
        if key == "payment_requests":
            v = {k: Invoice(**x) for k, x in v.items()}
        return v


def user_dir():
    if os.name == "posix":
        return os.path.join(os.environ["HOME"], ".bitcart-eth")
    elif "APPDATA" in os.environ:
        return os.path.join(os.environ["APPDATA"], "Bitcart-ETH")
    elif "LOCALAPPDATA" in os.environ:
        return os.path.join(os.environ["LOCALAPPDATA"], "Bitcart-ETH")


def str_to_bool(s):
    if isinstance(s, bool):
        return s
    s = s.lower()

    if s in STR_TO_BOOL_MAPPING:
        return STR_TO_BOOL_MAPPING[s]
    return False


def is_address(address):
    return Web3.isAddress(address) or Web3.isChecksumAddress(address)


class JSONEncoder(StorageJSONEncoder):
    def default(self, obj):
        if isinstance(obj, AttributeDict):
            return {k: v for k, v in obj.items()}
        if isinstance(obj, HexBytes):
            return str(obj.hex())
        return super().default(obj)


def to_dict(obj):
    return json.loads(json.dumps(obj, cls=JSONEncoder))


def get_exception_traceback(exc):
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


@dataclass
class KeyStore:
    key: str
    address: str = None
    public_key: str = None
    private_key: str = None
    seed: str = None
    account: Account = None

    def is_watching_only(self):
        return self.private_key is None

    def __post_init__(self):
        self.account = None
        try:
            self.account = Account.from_mnemonic(self.key)
            self.seed = self.key
        except Exception:
            try:
                self.account = Account.from_key(self.key)
            except Exception:
                try:
                    self.public_key = PublicKey.from_compressed_bytes(Web3.toBytes(hexstr=self.key))
                    self.address = self.public_key.to_checksum_address()
                except Exception:
                    if not is_address(self.key):
                        raise Exception("Error loading wallet: invalid address")
                    self.address = Web3.toChecksumAddress(self.key)
        if self.account:
            self.address = self.account.address
            self.private_key = self.account.key.hex()
            self.public_key = PublicKey.from_private(PrivateKey(Web3.toBytes(hexstr=self.private_key)))
        if self.public_key:
            self.public_key = Web3.toHex(self.public_key.to_compressed_bytes())

    def add_privkey(self, privkey):
        try:
            account = Account.from_key(privkey)
        except Exception:
            raise Exception("Invalid key provided")
        if account.address != self.address:
            raise Exception("Invalid private key imported: address mismatch")
        self.private_key = privkey
        self.account = account

    def has_seed(self):
        return bool(self.seed)

    @classmethod
    def load(cls, db):
        return cls(key=db.get("key", ""))

    def dump(self):
        return {"key": self.key}


@dataclass
class Invoice(StoredObject):
    message: str
    original_amount: Decimal
    amount: Decimal
    exp: int
    time: int
    height: int
    address: str
    id: str = None
    status: int = 0
    tx_hash: str = None

    @property
    def status_str(self):
        status_str = pr_tooltips[self.status]
        if self.status == PR_UNPAID:
            if self.exp > 0:
                expiration = self.exp + self.time
                status_str = "Expires at " + time.ctime(expiration)
        return status_str


@dataclass
class Wallet:
    web3: Web3
    db: WalletDB
    storage: Storage
    BLOCK_TIME: ClassVar[int]
    ADDRESS_CHECK_TIME: ClassVar[int]
    keystore: KeyStore = field(init=False)
    path: str = ""
    used_amounts: dict = field(default_factory=dict)
    receive_requests: dict = field(default_factory=dict)

    def __post_init__(self):
        self.keystore = KeyStore.load(self.db.get("keystore"))
        self.receive_requests = self.db.get_dict("payment_requests")
        self.used_amounts = self.db.get_dict("used_amounts")
        self.running = False
        self.loop = asyncio.get_event_loop()

    def save_db(self):
        if self.storage:
            self.db.write(self.storage)

    def start(self):
        self.running = True
        for req in self.get_sorted_requests():
            if req.status == PR_UNPAID and req.exp > 0 and req.time + req.exp < time.time():
                self.set_request_status(req.id, PR_EXPIRED)

    def clear_requests(self):
        self.receive_requests.clear()
        self.used_amounts.clear()
        self.save_db()

    def is_synchronized(self):  # because only one address is used due to eth specifics
        return True

    def is_watching_only(self):
        return self.keystore.is_watching_only()

    def get_private_key(self):
        if self.is_watching_only():
            raise Exception("This is a watching-only wallet")
        return self.keystore.private_key

    def import_private_key(self, privkey):
        self.keystore.add_privkey(privkey)

    @property
    def address(self):
        return self.keystore.address

    async def balance(self):
        return await self.web3.eth.get_balance(self.address)

    def stop(self):
        self.running = False

    async def make_payment_request(self, address, amount, message, expiration):
        amount = amount or Decimal()
        timestamp = int(time.time())
        expiration = expiration or 0
        return Invoice(
            address=address,
            message=message,
            time=timestamp,
            original_amount=amount,
            amount=self.generate_unique_amount(amount),
            exp=expiration,
            id=secrets.token_urlsafe(),
            height=await self.web3.eth.block_number,
        )

    def generate_unique_amount(self, amount: Decimal):
        add_low = 1
        add_high = 2
        cur_amount = amount
        while str(cur_amount) in self.used_amounts:
            cur_amount = amount + random.randint(add_low, add_high) * AMOUNTGEN_PRECISION
            if add_high < AMOUNTGEN_LIMIT:
                add_low = add_high + 1
                add_high *= 2
        return cur_amount

    def add_payment_request(self, req, save_db=True):
        self.receive_requests[req.id] = req
        self.used_amounts[str(req.amount)] = req.id
        if save_db:
            self.save_db()
        return req

    async def get_request_url(self, req):
        chain_id = await self.web3.eth.chain_id
        return f"ethereum:{req.address}@{chain_id}?value={req.amount}"

    async def export_request(self, req):
        d = {
            "id": req.id,
            "is_lightning": False,
            "amount_ETH": str(req.amount),
            "message": req.message,
            "timestamp": req.time,
            "expiration": req.exp,
            "status": req.status,
            "status_str": req.status_str,
        }
        if req.tx_hash:
            d["tx_hash"] = req.tx_hash
            d["confirmations"] = (
                await self.web3.eth.block_number
                - (await self.web3.eth.get_transaction_receipt(req.tx_hash))["blockNumber"]
                + 1
            )
        d["amount_wei"] = Web3.toWei(req.amount, "ether")
        d["address"] = req.address
        d["URI"] = await self.get_request_url(req)
        return d

    def get_request(self, key):
        try:
            amount = Decimal(key)
            key = self.used_amounts.get(str(amount))
        finally:
            return self.receive_requests.get(key)

    def remove_request(self, key):
        req = self.get_request(key)
        if not req:
            return False
        self.used_amounts.pop(str(req.amount), None)
        self.receive_requests.pop(req.id, None)
        self.save_db()
        return True

    def get_sorted_requests(self):
        out = [self.get_request(x) for x in self.receive_requests.keys()]
        out = [x for x in out if x is not None]
        out.sort(key=lambda x: x.time)
        return out

    def set_request_status(self, key, status, **kwargs):
        req = self.get_request(key)
        if not req:
            return None
        req.status = status
        for kwarg in kwargs:
            setattr(req, kwarg, kwargs[kwarg])
        self.add_payment_request(req, save_db=False)
        if status != PR_UNPAID:
            self.used_amounts.pop(str(req.amount), None)
        self.save_db()
        return req

    async def expired_task(self, req):
        left = req.time + req.exp - time.time() + 1  # to ensure it's already expired at that moment
        if left > 0:
            await asyncio.sleep(left)
        req = self.get_request(req.id)
        if req is None:
            return
        self.set_request_status(req.id, PR_EXPIRED)


class ETHDaemon(BaseDaemon):
    name = "ETH"
    BASE_SPEC_FILE = "daemons/spec/eth.json"
    DEFAULT_PORT = 5002
    ALIASES = {
        "add_invoice": "add_request",
        "clear_invoices": "clear_requests",
        "commands": "help",
        "get_invoice": "getrequest",
        "get_transaction": "gettransaction",
        "getunusedaddress": "getaddress",
        "list_invoices": "list_requests",
    }
    SKIP_NETWORK = ["getinfo"]

    VERSION = "4.1.5"  # version of electrum API with which we are "compatible"
    BLOCK_TIME = 5
    ADDRESS_CHECK_TIME = 60

    def __init__(self):
        super().__init__()
        Wallet.BLOCK_TIME = self.BLOCK_TIME
        Wallet.ADDRESS_CHECK_TIME = self.ADDRESS_CHECK_TIME
        self.latest_height = -1  # to avoid duplicate block notifications
        self.web3 = Web3(
            Web3.AsyncHTTPProvider(self.HTTP_HOST),
            modules={
                "eth": (AsyncEth,),
                "geth": (Geth, {"admin": (AsyncGethAdmin,)}),
            },
            middlewares=[],
        )
        # initialize wallet storages
        self.wallets = {}
        self.addresses = {}
        self.wallets_updates = {}
        # initialize not yet created network
        self.running = True
        self.loop = None

    def load_env(self):
        super().load_env()
        self.HTTP_HOST = self.config("HTTP_HOST", default=get_default_http_endpoint())

    async def on_startup(self, app):
        await super().on_startup(app)
        self.loop = asyncio.get_event_loop()
        self.latest_height = await self.web3.eth.block_number
        self.loop.create_task(self.process_pending())

    # TODO: retry mechanism?
    async def process_block(self, start_height, end_height):
        for block_number in range(start_height, end_height + 1):
            try:
                await self.trigger_event({"event": "new_block", "height": block_number}, None)
                for tx in (await self.web3.eth.get_block(block_number, full_transactions=True))["transactions"]:
                    try:
                        await self.process_transaction(tx)
                    except Exception:
                        if self.VERBOSE:
                            print(f"Error processing transaction {tx['hash'].hex()}:")
                            print(traceback.format_exc())
            except Exception:
                if self.VERBOSE:
                    print(f"Error processing block {block_number}:")
                    print(traceback.format_exc())

    async def process_transaction(self, tx):
        to = tx["to"]
        amount = Decimal(Web3.fromWei(tx["value"], "ether"))
        if to not in self.addresses:
            return
        wallet = self.addresses[to]
        tx_hash = str(tx["hash"].hex())
        await self.trigger_event({"event": "new_transaction", "tx": tx_hash}, wallet)
        if str(amount) in self.wallets[wallet].used_amounts:
            self.loop.create_task(self.process_payment(wallet, amount, tx_hash))

    async def process_pending(self):
        while self.running:
            try:
                current_height = await self.web3.eth.block_number
                tasks = []
                for block_number in range(self.latest_height + 1, current_height + 1, CHUNK_SIZE):
                    tasks.append(self.process_block(block_number, min(block_number + CHUNK_SIZE - 1, current_height)))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                if self.VERBOSE:
                    for task in results:
                        if isinstance(task, Exception):
                            print(get_exception_traceback(task))
                self.latest_height = current_height
            except Exception:
                if self.VERBOSE:
                    print("Error processing pending blocks:")
                    print(traceback.format_exc())
            await asyncio.sleep(self.BLOCK_TIME)

    async def trigger_event(self, data, wallet):
        for key in self.wallets:
            if not wallet or wallet == key:
                await self.notify_websockets(data, key)
                self.wallets_updates[key].append(data)

    async def process_payment(self, wallet, amount, tx_hash):
        try:
            req = self.wallets[wallet].set_request_status(amount, PR_PAID, tx_hash=tx_hash)
            await self.trigger_event(
                {"event": "new_payment", "address": req.address, "status": req.status, "status_str": req.status_str}, wallet
            )
        except Exception:
            if self.VERBOSE:
                print(f"Error processing successful payment {tx_hash} with {amount}:")
                print(traceback.format_exc())

    async def on_shutdown(self, app):
        self.running = False
        for wallet in self.wallets.values():
            wallet.stop()
        await super().on_shutdown(app)

    def get_method_data(self, method):
        return self.supported_methods[method]

    def get_exception_message(self, e):
        return get_exception_message(e)

    def get_datadir(self):
        base_dir = self.DATA_PATH or user_dir()
        datadir = os.path.join(base_dir, self.NET)
        os.makedirs(datadir, exist_ok=True)
        return datadir

    def get_wallet_path(self):
        path = os.path.join(self.get_datadir(), "wallets")
        os.makedirs(path, exist_ok=True)
        return path

    async def load_wallet(self, xpub):
        if xpub in self.wallets:
            return self.wallets[xpub]
        if not xpub:
            return None

        # get wallet on disk
        wallet_dir = self.get_wallet_path()
        wallet_path = os.path.join(wallet_dir, xpub)
        if not os.path.exists(wallet_path):
            self.restore(xpub)
        storage = Storage(wallet_path)
        db = WalletDB(storage.read())
        wallet = Wallet(self.web3, db, storage)
        wallet.start()
        self.wallets[xpub] = wallet
        self.wallets_updates[xpub] = []
        self.addresses[wallet.address] = xpub
        return wallet

    async def is_still_syncing(self, wallet=None):
        return not await self.web3.isConnected() or await self.web3.eth.syncing or (wallet and not wallet.is_synchronized())

    async def _get_wallet(self, id, req_method, xpub):
        wallet = error = None
        try:
            wallet = await self.load_wallet(xpub)
            if req_method in self.SKIP_NETWORK:
                return wallet, error
            while await self.is_still_syncing(wallet):
                await asyncio.sleep(0.1)
        except Exception as e:
            if self.VERBOSE:
                print(traceback.format_exc())
            if req_method not in self.supported_methods or self.supported_methods[req_method].requires_wallet:
                error_message = self.get_exception_message(e)
                error = JsonResponse(
                    code=self.get_error_code(error_message, fallback_code=-32005),
                    error=error_message,
                    id=id,
                )
        return wallet, error

    async def get_exec_method(self, id, req_method):
        error = None
        exec_method = None
        if req_method in self.supported_methods:
            exec_method = self.supported_methods[req_method]
        else:
            error = JsonResponse(code=-32601, error="Procedure not found", id=id)
        return exec_method, error

    async def get_exec_result(self, xpub, req_args, req_kwargs, exec_method):
        exec_method = functools.partial(exec_method, wallet=xpub)
        with hide_logging_errors(not self.VERBOSE):
            result = exec_method(*req_args, **req_kwargs)
            return await result if inspect.isawaitable(result) else result

    async def execute_method(self, id, req_method, req_args, req_kwargs):
        xpub = req_kwargs.pop("xpub", None)
        wallet, error = await self._get_wallet(id, req_method, xpub)
        if error:
            return error.send()
        exec_method, error = await self.get_exec_method(id, req_method)
        if error:
            return error.send()
        if self.get_method_data(req_method).requires_wallet and not xpub:
            return JsonResponse(code=-32000, error="Wallet not loaded", id=id).send()
        try:
            result = await self.get_exec_result(xpub, req_args, req_kwargs, exec_method)
            return JsonResponse(result=result, id=id).send()
        except BaseException as e:
            if self.VERBOSE:
                print(traceback.format_exc())
            error_message = self.get_exception_message(e)
            return JsonResponse(code=self.get_error_code(error_message), error=error_message, id=id).send()

    ### Methods ###

    @rpc
    async def add_peer(self, url, wallet=None):
        await self.web3.geth.admin.add_peer(url)

    @rpc(requires_wallet=True)
    async def add_request(self, amount, memo="", expiration=3600, force=False, wallet=None):
        amount = Decimal(amount)
        addr = self.wallets[wallet].address
        expiration = int(expiration) if expiration else None
        req = await self.wallets[wallet].make_payment_request(addr, amount, memo, expiration)
        self.wallets[wallet].add_payment_request(req)
        self.loop.create_task(self.wallets[wallet].expired_task(req))
        return await self.wallets[wallet].export_request(req)

    @rpc
    async def broadcast(self, tx, wallet=None):
        return to_dict(await self.web3.eth.send_raw_transaction(tx))

    @rpc(requires_wallet=True)
    def clear_requests(self, wallet):
        self.wallets[wallet].clear_requests()
        return True

    @rpc(requires_wallet=True)
    def close_wallet(self, wallet):
        self.wallets[wallet].stop()
        del self.wallets_updates[wallet]
        del self.addresses[self.wallets[wallet].address]
        del self.wallets[wallet]
        return True

    @rpc
    async def create(self, wallet=None, wallet_path=None):
        seed = self.make_seed()
        if not wallet_path:
            wallet_path = os.path.join(self.get_wallet_path(), seed)
        storage = Storage(wallet_path)
        if storage.file_exists():
            raise Exception("Remove the existing wallet first!")
        db = WalletDB("")
        keystore = KeyStore(seed)
        db.put("keystore", keystore.dump())
        wallet_obj = Wallet(self.web3, db, storage)
        wallet_obj.save_db()
        return {
            "seed": seed,
            "path": wallet_obj.storage.path,
            "msg": WRITE_DOWN_SEED_MESSAGE,
        }

    @rpc(requires_wallet=True)
    async def createnewaddress(self, *args, **kwargs):
        raise NotImplementedError(ONE_ADDRESS_MESSAGE)

    @rpc
    async def get_tx_status(self, tx, wallet=None):
        data = to_dict(await self.web3.eth.get_transaction_receipt(tx))
        data["confirmations"] = max(0, await self.web3.eth.block_number - data["blockNumber"] + 1)
        return data

    @rpc(requires_wallet=True)
    def getaddress(self, wallet):
        return self.wallets[wallet].address

    @rpc
    async def getaddressbalance(self, address, wallet=None):
        return await self.web3.eth.get_balance(address)

    @rpc
    def getaddresshistory(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc(requires_wallet=True)
    async def getbalance(self, wallet):
        return {"confirmed": await self.wallets[wallet].balance()}

    @rpc
    async def getfeerate(self, wallet=None):
        return await self.web3.eth.gas_price

    @rpc
    async def getinfo(self, wallet=None):
        if not await self.web3.isConnected():
            return {"connected": False, "path": "", "version": self.VERSION}
        numblocks = await self.web3.eth.block_number
        return {
            "blockchain_height": numblocks,
            "connected": await self.web3.isConnected(),
            "gas_price": await self.web3.eth.gas_price,
            "server": self.HTTP_HOST,
            "server_height": numblocks,
            "spv_nodes": len(await self.web3.geth.admin.peers()),
            "synchronized": not await self.web3.eth.syncing,
            "version": self.VERSION,
        }

    @rpc(requires_wallet=True)
    def getmasterprivate(self, *args, **kwargs):
        raise NotImplementedError(NO_MASTER_KEYS_MESSAGE)

    @rpc
    def getmerkle(self, *args, **kwargs):
        raise NotImplementedError(GET_PROOF_MESSAGE)

    @rpc(requires_wallet=True)
    def getmpk(self, *args, **kwargs):
        raise NotImplementedError(NO_MASTER_KEYS_MESSAGE)

    @rpc(requires_wallet=True)
    def getprivatekeys(self, *args, wallet=None):
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        return self.wallets[wallet].get_private_key()

    @rpc(requires_wallet=True)
    def getpubkeys(self, *args, wallet=None):
        return self.wallets[wallet].keystore.public_key

    @rpc(requires_wallet=True)
    async def getrequest(self, key, wallet):
        req = self.wallets[wallet].get_request(key)
        if not req:
            raise Exception("Request not found")
        return await self.wallets[wallet].export_request(req)

    @rpc(requires_wallet=True)
    def getseed(self, *args, wallet=None):
        if not self.wallets[wallet].keystore.has_seed():
            raise Exception("This wallet has no seed words")
        return self.wallets[wallet].keystore.seed

    @rpc
    def getservers(self, wallet=None):
        return [self.HTTP_HOST]

    @rpc
    async def gettransaction(self, tx, wallet=None):
        data = to_dict(await self.web3.eth.get_transaction(tx))
        data["confirmations"] = max(0, await self.web3.eth.block_number - data["blockNumber"] + 1)
        return data

    @rpc
    def help(self, wallet=None):
        return list(self.supported_methods.keys())

    @rpc(requires_wallet=True)
    async def history(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc(requires_wallet=True)
    def importprivkey(self, privkey, wallet):
        self.wallets[wallet].import_private_key(privkey)
        return "Successfully imported"

    @rpc(requires_wallet=True)
    def is_synchronized(self, wallet):
        return self.wallets[wallet].is_synchronized()

    @rpc(requires_wallet=True)
    def ismine(self, address, wallet):
        return address == self.wallets[wallet].address

    @rpc
    async def list_peers(self, wallet=None):
        return to_dict(await self.web3.geth.admin.peers())

    @rpc(requires_wallet=True)
    async def list_requests(self, pending=False, expired=False, paid=False, wallet=None):
        if pending:
            f = PR_UNPAID
        elif expired:
            f = PR_EXPIRED
        elif paid:
            f = PR_PAID
        else:
            f = None
        out = self.wallets[wallet].get_sorted_requests()
        if f is not None:
            out = [req for req in out if f.status == f]
        return [await self.wallets[wallet].export_request(x) for x in out]

    @rpc
    def list_wallets(self, wallet=None):
        return [
            {"path": wallet_obj.storage.path, "synchronized": wallet_obj.is_synchronized()}
            for wallet_obj in self.wallets.values()
        ]

    @rpc(requires_wallet=True)
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        unused, funded, balance = str_to_bool(unused), str_to_bool(funded), str_to_bool(balance)
        address = self.wallets[wallet].address
        addr_balance = await self.web3.eth.get_balance(address)
        ntxs = await self.web3.eth.get_transaction_count(address)
        if (unused and (addr_balance > 0 or ntxs > 0)) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, addr_balance)]
        else:
            return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", wallet=None):
        return Mnemonic(language).generate(nbits)

    async def get_fee_data(self):
        block = await self.web3.eth.get_block("latest")
        max_priority_fee = await self.web3.eth.max_priority_fee
        max_fee = block.baseFeePerGas * 2 + max_priority_fee
        return {"maxFeePerGas": max_fee, "maxPriorityFeePerGas": max_priority_fee}

    @rpc(requires_wallet=True)
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        address = self.wallets[wallet].address
        nonce = await self.web3.eth.get_transaction_count(address)
        tx_dict = {
            "type": "0x2",
            "from": self.wallets[wallet].address,
            "to": destination,
            "nonce": nonce,
            "value": Web3.toWei(amount, "ether"),
            "chainId": await self.web3.eth.chain_id,
            "gas": int(gas) if gas else 21000,
            **(await self.get_fee_data()),
        }
        if fee:
            tx_dict["maxFeePerGas"] = Web3.toWei(fee, "ether")
        if feerate:
            tx_dict["maxPriorityFeePerGas"] = Web3.toWei(feerate, "gwei")
        if unsigned:
            return tx_dict
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        return self._sign_transaction(tx_dict, self.wallets[wallet].keystore.private_key)

    @rpc(requires_wallet=True)
    def removelocaltx(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc
    def restore(self, text, wallet=None, wallet_path=None):
        if not wallet_path:
            wallet_path = os.path.join(self.get_wallet_path(), text)
        try:
            keystore = KeyStore(text)
        except Exception as e:
            raise Exception("Invalid key provided") from e
        storage = Storage(wallet_path)
        if storage.file_exists():
            raise Exception("Remove the existing wallet first!")
        db = WalletDB("")
        db.put("keystore", keystore.dump())
        wallet_obj = Wallet(self.web3, db, storage)
        wallet_obj.save_db()
        return {
            "path": wallet_obj.storage.path,
            "msg": "",
        }

    @rpc(requires_wallet=True)
    def rmrequest(self, key, wallet):
        return self.wallets[wallet].remove_request(key)

    @rpc(requires_wallet=True)
    def signmessage(self, address=None, message=None, wallet=None):
        # Mimic electrum API
        if not address and not message:
            raise ValueError("No message specified")
        if not message:
            message = address
        return to_dict(Account.sign_message(encode_defunct(text=message), private_key=self.wallets[wallet].key).signature)

    def _sign_transaction(self, tx, private_key):
        tx_dict = tx
        if isinstance(tx, str):
            try:
                tx_dict = json.loads(tx)
            except json.JSONDecodeError as e:
                raise Exception("Invalid transaction") from e
        return to_dict(Account.sign_transaction(tx_dict, private_key=private_key).rawTransaction)

    @rpc(requires_wallet=True)
    def signtransaction(self, tx, wallet=None):
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        return self._sign_transaction(tx, self.wallets[wallet].keystore.private_key)

    @rpc
    def signtransaction_with_privkey(self, tx, privkey, wallet=None):
        return self._sign_transaction(tx, privkey)

    @rpc
    def validateaddress(self, address, wallet=None):
        return is_address(address)

    @rpc
    def verifymessage(self, address, signature, message, wallet=None):
        return Web3.toChecksumAddress(
            Account.recover_message(encode_defunct(text=message), signature=signature)
        ) == Web3.toChecksumAddress(address)

    @rpc
    def version(self, wallet=None):
        return self.VERSION

    ### BitcartCC methods ###

    @rpc(requires_wallet=True)
    def get_updates(self, wallet):
        updates = self.wallets_updates[wallet]
        self.wallets_updates[wallet] = []
        return updates


if __name__ == "__main__":
    daemon = ETHDaemon()
    daemon.start()
