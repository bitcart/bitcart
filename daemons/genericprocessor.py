from base import BaseDaemon  # isort: skip

import asyncio
import functools
import inspect
import json
import os
import secrets
import time
import traceback
from abc import ABCMeta, abstractmethod
from collections import defaultdict, deque
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal

from aiohttp import ClientSession
from logger import get_logger
from storage import ConfigDB as StorageConfigDB
from storage import JSONEncoder as StorageJSONEncoder
from storage import Storage, StoredDBProperty, StoredObject, StoredProperty, decimal_to_string
from storage import WalletDB as StorageWalletDB
from utils import CastingDataclass, JsonResponse, get_exception_message, get_function_header, hide_logging_errors, rpc

logger = get_logger(__name__)

NO_HISTORY_MESSAGE = "We don't access transaction history to remain lightweight"
WRITE_DOWN_SEED_MESSAGE = "Please keep your seed in a safe place; if you lose it, you will not be able to restore your wallet."
ONE_ADDRESS_MESSAGE = "We only support one address per wallet because of current blockchain specifics"
GET_PROOF_MESSAGE = "Currrent blockchain doesn't support get_proof correctly for now"
NO_MASTER_KEYS_MESSAGE = "As we use only one address per wallet, address keys are used, but not the xprv/xpub"


NOOP_PATH = object()

CHUNK_SIZE = 30
AMOUNTGEN_LIMIT = 10**9


# statuses of payment requests
PR_UNPAID = 0  # invoice amt not reached by txs in mempool+chain.
PR_EXPIRED = 1  # invoice is unpaid and expiry time reached
PR_PAID = 3  # paid and mined (1 conf).
PR_UNCONFIRMED = 7

daemon_ctx: ContextVar[BaseDaemon] = ContextVar("daemon")


class BlockchainFeatures(metaclass=ABCMeta):
    def __init__(self, rpc):
        self.rpc = rpc

    @abstractmethod
    def get_block_number(self) -> int:
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        pass

    @abstractmethod
    def get_transaction(self, tx) -> dict:
        pass

    @abstractmethod
    def get_tx_receipt(self, tx) -> dict:
        pass

    @abstractmethod
    async def get_confirmations(self, tx_hash) -> int:
        pass

    @abstractmethod
    def get_balance(self, address) -> Decimal:
        pass

    @abstractmethod
    def get_block(self, block, *args, **kwargs) -> dict:
        pass

    @abstractmethod
    async def get_block_txes(self, block) -> list:
        pass

    @abstractmethod
    def is_address(self, address) -> bool:
        pass

    @abstractmethod
    def normalize_address(self, address) -> str:
        pass

    @abstractmethod
    async def get_payment_uri(self, address, amount, divisibility, contract=None) -> str:
        pass

    @abstractmethod
    async def process_tx_data(self, data) -> "Transaction":
        pass

    @abstractmethod
    def get_tx_hash(self, tx_data) -> str:
        pass

    @abstractmethod
    def get_gas_price(self) -> int:
        pass

    async def debug_trace_block(self, block_number):
        return None

    def get_wallet_key(self, xpub, *args, **kwargs):
        return xpub

    def to_dict(self, obj):
        return json.loads(StorageJSONEncoder(precision=daemon_ctx.get().DIVISIBILITY).encode(obj))

    @abstractmethod
    def current_server(self):
        pass


pr_tooltips = {PR_UNPAID: "Unpaid", PR_PAID: "Paid", PR_EXPIRED: "Expired", PR_UNCONFIRMED: "Unconfirmed"}


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
    STORAGE_VERSION = 3

    def _convert_dict(self, path, key, v):
        if key == "payment_requests":
            v = {k: daemon_ctx.get().INVOICE_CLASS(**x) for k, x in v.items()}
        return v

    def _should_convert_to_stored_dict(self, key) -> bool:
        return key != "keystore"

    def run_upgrades(self):
        self._convert_version_2()
        self._convert_version_3()

    def _convert_version_2(self):
        if not self._is_upgrade_method_needed(1, 1):
            return
        invoices = self.data.get("payment_requests", {})
        for key in invoices:
            invoices[key].pop("original_amount", None)
            if "sent_amount" not in invoices[key]:
                invoices[key]["sent_amount"] = decimal_to_string(Decimal(0))
        self.put("version", 2)

    def _convert_version_3(self):
        if not self._is_upgrade_method_needed(2, 2):
            return
        invoices = self.data.get("payment_requests", {})
        for key in invoices:
            tx_hashes = []
            if "tx_hash" in invoices[key]:
                tx_hash = invoices[key].pop("tx_hash")
                if tx_hash is not None:
                    tx_hashes.append(tx_hash)
            invoices[key]["tx_hashes"] = tx_hashes
        self.put("version", 3)


class ConfigDB(StorageConfigDB):
    STORAGE_VERSION = 1


def str_to_bool(s):
    if isinstance(s, bool):
        return s
    s = s.lower()

    if s in STR_TO_BOOL_MAPPING:
        return STR_TO_BOOL_MAPPING[s]
    return False


def get_exception_traceback(exc):
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def from_wei(value: int, precision=None) -> Decimal:
    if precision is None:
        precision = daemon_ctx.get().DIVISIBILITY
    if value == 0:
        return Decimal(0)
    return Decimal(value) / Decimal(10**precision)


def to_wei(value: Decimal, precision=None) -> int:
    if precision is None:
        precision = daemon_ctx.get().DIVISIBILITY
    if value == Decimal(0):
        return 0
    return int(Decimal(value) * Decimal(10**precision))


@dataclass
class Transaction:
    hash: str
    from_addr: str
    to: str
    value: int
    contract: str = None
    divisibility: int = None


@dataclass
class KeyStore(metaclass=ABCMeta):
    key: str
    address: str = None
    public_key: str = None
    private_key: str = None
    seed: str = None
    contract: str = None

    def is_watching_only(self):
        return self.private_key is None

    def __post_init__(self):
        self.load_account_from_key()

    @abstractmethod
    def load_account_from_key(self):
        pass

    @abstractmethod
    def add_privkey(self, privkey):
        pass

    def has_seed(self):
        return bool(self.seed)

    @classmethod
    def load(cls, db):
        return cls(key=db.get("key", ""))

    def dump(self):
        return {"key": self.key}


@dataclass
class Invoice(CastingDataclass, StoredObject):
    message: str
    sent_amount: Decimal
    amount: Decimal
    exp: int
    time: int
    height: int
    address: str
    payment_address: str = None
    id: str = None
    status: int = 0
    tx_hashes: list = field(default_factory=list)
    contract: str = None

    @property
    def status_str(self):
        status_str = pr_tooltips[self.status]
        if self.status == PR_UNPAID and self.exp > 0:
            expiration = self.exp + self.time
            status_str = "Expires at " + time.ctime(expiration)
        return status_str


@dataclass
class Wallet:
    coin: BlockchainFeatures
    db: WalletDB
    storage: Storage
    keystore: KeyStore = field(init=False)
    request_addresses: dict = field(default_factory=dict)
    receive_requests: dict = field(default_factory=dict)
    symbol: str = None
    divisibility: int = None

    latest_height = StoredDBProperty("latest_height", -1)

    def __post_init__(self):
        if self.symbol is None:
            self.symbol = daemon_ctx.get().name
        if self.divisibility is None:
            self.divisibility = daemon_ctx.get().DIVISIBILITY
        self.keystore = daemon_ctx.get().KEYSTORE_CLASS.load(self.db.get("keystore"))
        self.receive_requests = self.db.get_dict("payment_requests")
        self.request_addresses = self.db.get_dict("request_addresses")
        self.running = False
        self.loop = asyncio.get_event_loop()
        self.synchronized = False

    def save_db(self):
        if self.storage:
            self.db.write(self.storage)

    async def _start_init_vars(self):
        if self.latest_height == -1:
            self.latest_height = await self.coin.get_block_number()

    async def _start_process_pending(self, blocks, current_height):
        for block in blocks:
            for tx in block:
                try:
                    await daemon_ctx.get().process_transaction(tx)
                except Exception:
                    logger.error(f"Error processing transaction {self.coin.get_tx_hash(tx)}:")
                    logger.error(traceback.format_exc())

    async def start(self, blocks):
        first_start = self.latest_height == -1
        await self._start_init_vars()

        self.running = True
        # process onchain transactions
        current_height = await self.coin.get_block_number()
        if not first_start and not daemon_ctx.get().NO_DOWNTIME_PROCESSING:
            await self._start_process_pending(blocks, current_height)

        self.latest_height = current_height
        for req in self.get_sorted_requests():
            if req.status == PR_UNPAID:
                if req.exp > 0 and req.time + req.exp < time.time():
                    self.set_request_status(req.id, PR_EXPIRED)
                else:
                    self.loop.create_task(self.expired_task(req))
        self.synchronized = True

    def clear_requests(self):
        self.receive_requests.clear()
        self.request_addresses.clear()
        self.save_db()

    def is_synchronized(self):
        return self.synchronized

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

    @property
    def contract_addr(self):
        return None

    @property
    def wallet_key(self):
        return self.coin.get_wallet_key(self.keystore.key, self.contract_addr)

    async def balance(self):
        return await self.coin.get_balance(self.address)

    def stop(self, block_number):
        self.running = False
        self.latest_height = block_number

    async def make_payment_request(self, address, amount, message, expiration):
        amount = amount or Decimal()
        if amount < 0:
            raise Exception("Out of bounds amount")
        timestamp = int(time.time())
        expiration = expiration or 0
        return await self.create_payment_request_object(address, amount, message, expiration, timestamp)

    async def create_payment_request_object(self, address, amount, message, expiration, timestamp):
        return Invoice(
            address=address,
            message=message,
            time=timestamp,
            amount=amount,
            sent_amount=Decimal(0),
            exp=expiration,
            id=secrets.token_urlsafe(),
            height=await self.coin.get_block_number(),
        )

    def add_payment_request(self, req, save_db=True):
        self.receive_requests[req.id] = req
        if save_db:
            self.save_db()
        return req

    async def export_request(self, req):
        d = {
            "id": req.id,
            "request_id": req.id,  # to distinguish from non-functional id in some coins
            "is_lightning": False,
            f"amount_{self.symbol}": decimal_to_string(req.amount, self.divisibility),
            "sent_amount": decimal_to_string(req.sent_amount, self.divisibility),
            "message": req.message,
            "timestamp": req.time,
            "expiration": req.time + req.exp if req.exp else 0,
            "payment_address": req.payment_address,
            "status": req.status,
            "status_str": req.status_str,
        }
        if req.tx_hashes:
            d["tx_hashes"] = req.tx_hashes
            d["confirmations"] = await self.coin.get_confirmations(req.tx_hashes[0])
        d[f"amount_{daemon_ctx.get().UNIT}"] = to_wei(req.amount, self.divisibility)
        d["address"] = req.address
        d["URI"] = await self.get_payment_uri(req.address, req.amount)
        return d

    async def get_payment_uri(self, address, amount):
        return await self.coin.get_payment_uri(address, amount, self.divisibility, contract=getattr(self, "contract", None))

    def get_request(self, key):
        key = self.request_addresses.get(key, key)
        return self.receive_requests.get(key)

    def remove_from_detection_dict(self, req):
        self.request_addresses.pop(req.payment_address, None)

    def remove_request(self, key):
        req = self.get_request(key)
        if not req:
            return False
        self.remove_from_detection_dict(req)
        self.receive_requests.pop(req.id, None)
        self.save_db()
        return True

    def get_sorted_requests(self):
        out = [self.get_request(x) for x in self.receive_requests]
        out = [x for x in out if x is not None]
        out.sort(key=lambda x: x.time)
        return out

    def set_request_status(self, key, status, tx_hash=None, **kwargs):
        req = self.get_request(key)
        if not req:
            return None
        if req.status == PR_PAID:  # immutable
            return req
        if req.status == PR_UNCONFIRMED and status == PR_EXPIRED:  # once mined, wait forever
            return req
        req.status = status
        if tx_hash is not None:
            req.tx_hashes.append(tx_hash)
            req.tx_hashes = list(dict.fromkeys(req.tx_hashes))  # remove duplicates
        for kwarg in kwargs:
            setattr(req, kwarg, kwargs[kwarg])
        self.add_payment_request(req, save_db=False)
        if status in (PR_PAID, PR_EXPIRED):
            self.remove_from_detection_dict(req)
        self.save_db()
        return req

    def set_request_address(self, key, address):
        req = self.get_request(key)
        if not req:
            return None
        self.remove_from_detection_dict(req)
        req.payment_address = address
        self.request_addresses[address] = req.id
        self.add_payment_request(req)
        return req

    async def expired_task(self, req):
        left = req.time + req.exp - time.time() + 1  # to ensure it's already expired at that moment
        if left > 0:
            await asyncio.sleep(left)
        req = self.get_request(req.id)
        if req is None:
            return
        self.set_request_status(req.id, PR_EXPIRED)

    async def process_new_payment(self, lookup_field, tx, amount, wallet):
        req = self.get_request(lookup_field)
        if req is None or req.status != PR_UNPAID or tx.hash in req.tx_hashes:
            return
        req.sent_amount += amount
        await self.process_payment(
            wallet,
            req.id,
            tx_hash=tx.hash,
            status=PR_PAID if req.sent_amount >= req.amount else PR_UNPAID,
            contract=tx.contract,
        )

    async def process_payment(self, wallet, key, tx_hash, contract=None, status=PR_PAID):
        try:
            req = self.set_request_status(key, status, tx_hash=tx_hash, contract=contract)
            await daemon_ctx.get().trigger_event(
                {
                    "event": "new_payment",
                    "address": req.id,
                    "status": req.status,
                    "status_str": req.status_str,
                    "tx_hashes": req.tx_hashes,
                    "sent_amount": decimal_to_string(req.sent_amount, self.divisibility),
                    "contract": contract,
                },
                wallet,
            )
        except Exception:
            logger.error(f"Error processing successful payment {tx_hash} with {key}:")
            logger.error(traceback.format_exc())


class BlockProcessorDaemon(BaseDaemon, metaclass=ABCMeta):
    name: str
    BASE_SPEC_FILE: str
    DEFAULT_PORT: int
    ALIASES = {
        "add_invoice": "add_request",
        "clear_invoices": "clear_requests",
        "commands": "help",
        "get_invoice": "getrequest",
        "get_request": "getrequest",
        "get_transaction": "gettransaction",
        "getaddressbalance_wallet": "getaddressbalance",
        "getunusedaddress": "getaddress",
        "list_invoices": "list_requests",
    }
    SKIP_NETWORK = ["getinfo"]

    DIVISIBILITY: int
    BLOCK_TIME: int
    DEFAULT_MAX_SYNC_BLOCKS: int
    AMOUNTGEN_DIVISIBILITY = 8  # Max number of decimal places to use for amounts generation

    SPEED_MULTIPLIERS = {"network": 1, "regular": 1.25, "fast": 1.5}

    VERSION = "4.5.0"  # version of electrum API with which we are "compatible"

    KEYSTORE_CLASS = KeyStore
    WALLET_CLASS = Wallet
    INVOICE_CLASS = Invoice

    coin: BlockchainFeatures  # set by create_coin()
    UNIT: str

    ARCHIVE_SUPPORTED = False

    latest_height = StoredProperty("latest_height", -1)

    def __init__(self):
        self._should_check_seed_server = False
        super().__init__()
        daemon_ctx.set(self)
        self.latest_blocks = deque(maxlen=self.MAX_SYNC_BLOCKS)
        self.config_path = os.path.join(self.get_datadir(), "config")
        self.config = ConfigDB(self.config_path)
        self.env_update_hooks = {"server": self.update_server}  # TODO: add a way to extend
        # initialize wallet storages
        self.wallets = {}
        self.addresses = defaultdict(set)
        self.wallet_locks = defaultdict(asyncio.Lock)
        self.wallets_updates = {}
        # initialize not yet created network
        self.running = True
        self.loop = None
        self.synchronized = False

    async def update_server(self, start_new=True):
        self.SERVER = self.SERVER.split(",")
        if not start_new:
            return
        await self.shutdown_coin()
        await self.create_coin()

    @abstractmethod
    async def create_coin(self, archive=False):
        pass

    @abstractmethod
    async def shutdown_coin(self, final=False, archive_only=False):
        pass

    @abstractmethod
    def get_default_server_url(self):
        pass

    def load_env(self):
        super().load_env()
        self.SEED_SERVER = self.env("SEED_SERVER", default="")
        self.SEED_SERVER_REFRESH_INTERVAL = self.env("SEED_SERVER_REFRESH_INTERVAL", cast=int, default=60 * 60)
        self.SERVER = self.env("SERVER", default=self.get_default_server_url()).split(",")
        if len(self.SERVER) == 1 and self.SERVER[0] == self.SEED_SERVER:
            self._should_check_seed_server = True
        max_sync_hours = self.env("MAX_SYNC_HOURS", cast=int, default=1)
        self.MAX_SYNC_BLOCKS = max_sync_hours * self.DEFAULT_MAX_SYNC_BLOCKS
        self.TX_SPEED = self.env("TX_SPEED", cast=str, default="network").lower()
        try:
            self.SPEED_MULTIPLIER = float(self.TX_SPEED)
        except ValueError:
            if self.TX_SPEED not in self.SPEED_MULTIPLIERS:
                raise ValueError(
                    f"Invalid TX_SPEED: {self.TX_SPEED}. Valid values: {', '.join(self.SPEED_MULTIPLIERS.keys())}"
                ) from None
            self.SPEED_MULTIPLIER = self.SPEED_MULTIPLIERS[self.TX_SPEED]
        self.NO_DOWNTIME_PROCESSING = self.env("NO_DOWNTIME_PROCESSING", cast=bool, default=False)

    async def on_startup(self, app):
        await super().on_startup(app)
        if not await self.maybe_update_seed_server():
            await self.create_coin()
        self.loop = asyncio.get_event_loop()
        if self.latest_height == -1:
            self.latest_height = await self.coin.get_block_number()
        self.loop.create_task(self.process_pending())
        self.loop.create_task(self.update_seed_servers())

    async def maybe_update_seed_server(self, start_new=True):
        if self.SEED_SERVER and self._should_check_seed_server:
            max_attempts = 7
            for attempt in range(max_attempts):
                try:
                    async with ClientSession() as session, session.get(f"{self.SEED_SERVER}/{self.name.lower()}") as response:
                        response.raise_for_status()
                        new_servers = await response.json()
                        if new_servers.split(",") == self.SERVER:
                            return False
                        self.SERVER = new_servers
                        if self.ARCHIVE_SUPPORTED and getattr(self, "_should_archive_seed_server", False):
                            self.ARCHIVE_SERVER = self.SERVER
                            await self.update_archive_server(start_new=start_new)
                        await self.update_server(start_new=start_new)
                        return True
                except Exception:
                    logger.error(f"Error updating seed servers (attempt {attempt + 1}/{max_attempts}):")
                    logger.error(traceback.format_exc())
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    if len(self.SERVER) == 1 and self.SERVER[0] == self.SEED_SERVER:
                        self.SERVER = self.get_default_server_url()
                        if hasattr(self, "ARCHIVE_SERVER") and getattr(self, "_should_archive_seed_server", False):
                            self.ARCHIVE_SERVER = self.SERVER
                            await self.update_archive_server(start_new=start_new)
                        await self.update_server(start_new=start_new)
                        return True
        return False

    async def update_seed_servers(self):
        while self.running:
            await self.maybe_update_seed_server()
            await asyncio.sleep(self.SEED_SERVER_REFRESH_INTERVAL)

    async def process_transaction(self, tx):
        if tx.divisibility is None:
            tx.divisibility = self.DIVISIBILITY
        to = tx.to
        amount = from_wei(tx.value, tx.divisibility)
        if to not in self.addresses:
            return
        for wallet in self.addresses[to]:
            wallet_contract = self.wallets[wallet].contract_addr
            if tx.contract != wallet_contract:
                continue
            await self.trigger_event(
                {
                    "event": "new_transaction",
                    "tx": tx.hash,
                    "from_address": tx.from_addr,
                    "to": tx.to,
                    "amount": decimal_to_string(amount, tx.divisibility),
                    "contract": tx.contract,
                },
                wallet,
            )
            if tx.from_addr in self.wallets[wallet].request_addresses:
                self.loop.create_task(self.wallets[wallet].process_new_payment(tx.from_addr, tx, amount, wallet))

    async def process_tx_task(self, tx_data, semaphore):
        async with semaphore:
            try:
                tx = await self.coin.process_tx_data(tx_data)
                if tx is not None:
                    await self.process_transaction(tx)
                return tx
            except Exception:
                logger.error(f"Error processing transaction {self.coin.get_tx_hash(tx_data)}:")
                logger.error(traceback.format_exc())

    async def process_block(self, start_height, end_height):
        for block_number in range(start_height, end_height + 1):
            try:
                await self.trigger_event({"event": "new_block", "height": block_number}, None)
                if getattr(self, "trace_available", False):
                    await self.trace_queue.put(block_number)
                block = await self.coin.get_block_txes(block_number)
                transactions = []
                tasks = []
                semaphore = asyncio.Semaphore(20)
                for tx_data in block:
                    tasks.append(self.process_tx_task(tx_data, semaphore))
                results = await asyncio.gather(*tasks)
                for res in results:
                    if res is not None:
                        transactions.append(res)
                self.latest_blocks.append(transactions)
            except Exception:
                logger.error(f"Error processing block {block_number}:")
                logger.error(traceback.format_exc())

    async def process_block_by_chunks(self, start_height, end_height):
        tasks = []
        for block_number in range(start_height, end_height + 1, CHUNK_SIZE):
            tasks.append(self.process_block(block_number, min(block_number + CHUNK_SIZE - 1, end_height)))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        if self.VERBOSE:
            for task in results:
                if isinstance(task, Exception):
                    logger.error(get_exception_traceback(task))

    async def process_pending(self):
        while self.running:
            try:
                current_height = await self.coin.get_block_number()
                # process at max 300 blocks since last processed block, fetched by chunks
                await self.process_block_by_chunks(
                    self.latest_height + 1, min(self.latest_height + self.MAX_SYNC_BLOCKS, current_height)
                )
                self.latest_height = current_height
                self.synchronized = True  # set it once, as we just need to ensure initial sync was done
            except Exception:
                logger.error("Error processing pending blocks:")
                logger.error(traceback.format_exc())
            await asyncio.sleep(self.BLOCK_TIME)

    async def trigger_event(self, data, wallet):
        await self.notify_websockets(data, wallet)
        if self.POLLING_CAP == 0:
            return
        if wallet:
            self.wallets_updates[wallet].append(data)
        else:
            for key in self.wallets.copy():
                self.wallets_updates[key].append(data)

    async def on_shutdown(self, app):
        self.running = False
        block_number = await self.coin.get_block_number()
        for wallet in list(self.wallets.values()):
            wallet.stop(block_number)
        await self.shutdown_coin(final=True)
        await super().on_shutdown(app)

    def get_method_data(self, method):
        return self.supported_methods[method]

    def get_exception_message(self, e):
        return get_exception_message(e)

    def user_dir(self):
        if os.name == "posix":
            return os.path.join(os.environ["HOME"], f".bitcart-{self.name.lower()}")
        if "APPDATA" in os.environ:
            return os.path.join(os.environ["APPDATA"], f"Bitcart-{self.name.upper()}")
        if "LOCALAPPDATA" in os.environ:
            return os.path.join(os.environ["LOCALAPPDATA"], f"Bitcart-{self.name.upper()}")

    def get_datadir(self):
        base_dir = self.DATA_PATH or self.user_dir()
        datadir = os.path.join(base_dir, self.NET)
        os.makedirs(datadir, exist_ok=True)
        return datadir

    def get_wallet_path(self):
        path = os.path.join(self.get_datadir(), "wallets")
        os.makedirs(path, exist_ok=True)
        return path

    @abstractmethod
    async def load_wallet(self, xpub, contract, diskless=False, extra_params=None):
        pass

    async def is_still_syncing(self, wallet=None):
        if self.NO_SYNC_WAIT:
            return False
        return wallet and not wallet.is_synchronized()

    async def _get_wallet(self, req_id, req_method, xpub, contract, diskless=False, extra_params=None):
        if extra_params is None:
            extra_params = {}
        wallet = error = None
        try:
            should_skip = req_method not in self.supported_methods or not self.supported_methods[req_method].requires_network
            if not self.NO_SYNC_WAIT:
                while not should_skip and not self.synchronized:  # wait for initial sync to fetch blocks
                    await asyncio.sleep(0.1)
            wallet = await self.load_wallet(xpub, contract, diskless=diskless, extra_params=extra_params)
            if should_skip:
                return wallet, error
            while await self.is_still_syncing(wallet):
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(traceback.format_exc())
            if req_method not in self.supported_methods or self.supported_methods[req_method].requires_wallet:
                error_message = self.get_exception_message(e)
                error = JsonResponse(
                    code=self.get_error_code(error_message, fallback_code=-32005),
                    error=error_message,
                    id=req_id,
                )
        return wallet, error

    async def get_exec_method(self, req_id, req_method):
        error = None
        exec_method = None
        if req_method in self.supported_methods:
            exec_method = self.supported_methods[req_method]
        else:
            error = JsonResponse(code=-32601, error="Procedure not found", id=req_id)
        return exec_method, error

    async def get_exec_result(self, xpub, req_args, req_kwargs, exec_method):
        exec_method = functools.partial(exec_method, wallet=xpub)
        with hide_logging_errors(not self.VERBOSE):
            result = exec_method(*req_args, **req_kwargs)
            return await result if inspect.isawaitable(result) else result

    async def execute_method(self, req_id, req_method, xpub, contract, extra_params, req_args, req_kwargs):
        wallet_key = self.coin.get_wallet_key(xpub, contract, **extra_params)
        try:
            if xpub:
                await self.wallet_locks[wallet_key].acquire()
            wallet, error = await self._get_wallet(
                req_id, req_method, xpub, contract, diskless=extra_params.get("diskless", False), extra_params=extra_params
            )
            if error:
                return error.send()
            exec_method, error = await self.get_exec_method(req_id, req_method)
            if error:
                return error.send()
            if self.get_method_data(req_method).requires_wallet and not xpub:
                return JsonResponse(code=-32000, error="Wallet not loaded", id=req_id).send()
            try:
                result = await self.get_exec_result(wallet_key, req_args, req_kwargs, exec_method)
                return JsonResponse(result=result, id=req_id).send()
            except BaseException as e:
                if not extra_params.get("quiet_mode"):
                    logger.error(traceback.format_exc())
                error_message = self.get_exception_message(e)
                return JsonResponse(code=self.get_error_code(error_message), error=error_message, id=req_id).send()
            finally:
                if extra_params.get("one_time", False):
                    await self.close_wallet_impl(wallet_key, locked=True)
        finally:
            if xpub:
                self.wallet_locks[wallet_key].release()

    #########
    # Methods
    #########

    @rpc(requires_network=True)
    @abstractmethod
    async def add_peer(self, url, wallet=None):
        pass

    @rpc(requires_wallet=True, requires_network=True)
    async def add_request(self, amount, memo="", expiration=3600, force=False, wallet=None):
        amount = Decimal(amount)
        addr = self.wallets[wallet].address
        expiration = int(expiration) if expiration else None
        req = await self.wallets[wallet].make_payment_request(addr, amount, memo, expiration)
        self.wallets[wallet].add_payment_request(req)
        self.loop.create_task(self.wallets[wallet].expired_task(req))
        return await self.wallets[wallet].export_request(req)

    async def _parse_and_load(self, semaphore, xpub):
        async with semaphore:
            xpub, contract, extra_params = self.parse_xpub(xpub)
            await self.load_wallet(xpub, contract, diskless=extra_params.get("diskless", False), extra_params=extra_params)

    @rpc
    async def batch_load(self, wallets, background=False, wallet=None):
        if not isinstance(wallets, list):
            wallets = json.loads(wallets)
        semaphore = asyncio.BoundedSemaphore(100)
        coro = asyncio.gather(*(self._parse_and_load(semaphore, w) for w in wallets))
        if not str_to_bool(background):
            await coro
        return True

    @rpc(requires_network=True)
    @abstractmethod
    async def broadcast(self, tx, wallet=None):
        pass

    @rpc(requires_wallet=True)
    def clear_requests(self, wallet):
        self.wallets[wallet].clear_requests()
        return True

    async def close_wallet_impl(self, key, locked=False):
        try:
            if not locked:
                await self.wallet_locks[key].acquire()
            if key not in self.wallets:
                return False
            block_number = await self.coin.get_block_number()
            self.wallets[key].stop(block_number)
            self.wallets_updates.pop(key, None)
            address = self.wallets[key].address
            self.addresses[address].discard(key)
            if not self.addresses[address]:
                self.addresses.pop(address, None)
            self.wallets.pop(key, None)
            return True
        finally:
            if not locked:
                self.wallet_locks[key].release()

    @rpc(requires_network=True)
    async def close_wallet(self, key=None, wallet=None):
        locked = bool(wallet)
        key = wallet or key
        return await self.close_wallet_impl(key, locked=locked)

    @rpc
    async def create(self, wallet=None, wallet_path=None):
        seed = self.make_seed()
        if not wallet_path:
            wallet_path = os.path.join(self.get_wallet_path(), seed)
        storage = Storage(wallet_path)
        if storage.file_exists():
            raise Exception("Remove the existing wallet first!")
        db = WalletDB("")
        keystore = daemon_ctx.get().KEYSTORE_CLASS(seed)
        db.put("keystore", keystore.dump())
        wallet_obj = self.WALLET_CLASS(self.coin, db, storage)
        wallet_obj.save_db()
        return {
            "seed": seed,
            "path": wallet_obj.storage.path,
            "msg": WRITE_DOWN_SEED_MESSAGE,
        }

    @rpc
    async def createnewaddress(self, *args, **kwargs):
        raise NotImplementedError(ONE_ADDRESS_MESSAGE)

    @rpc(requires_network=True)
    @abstractmethod
    async def get_default_fee(self, tx, wallet=None):
        pass

    @rpc(requires_wallet=True)
    async def get_payment_uri(self, address, amount, wallet):
        return await self.wallets[wallet].get_payment_uri(address, amount)

    @rpc
    @abstractmethod
    def get_tx_hash(self, tx_data, wallet=None):
        pass

    @rpc
    @abstractmethod
    def get_tx_size(self, tx_data, wallet=None):
        pass

    @rpc(requires_network=True)
    async def get_tx_status(self, tx, wallet=None):
        data = self.coin.to_dict(await self.coin.get_tx_receipt(tx))
        data["confirmations"] = await self.coin.get_confirmations(tx, data)
        return data

    @rpc(requires_wallet=True, requires_network=True)
    def get_updates(self, wallet):
        updates = self.wallets_updates[wallet]
        self.wallets_updates[wallet] = deque(maxlen=self.POLLING_CAP)
        return list(updates)

    @rpc(requires_network=True)
    @abstractmethod
    async def get_used_fee(self, tx_hash, wallet=None):
        pass

    @rpc(requires_wallet=True)
    def getaddress(self, wallet):
        return self.wallets[wallet].address

    @rpc(requires_network=True)
    async def getaddressbalance(self, address, wallet=None):
        return decimal_to_string(await self.coin.get_balance(address), self.DIVISIBILITY)

    @rpc
    def getaddresshistory(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc(requires_wallet=True, requires_network=True)
    async def getbalance(self, wallet):
        return {"confirmed": decimal_to_string(await self.wallets[wallet].balance(), self.wallets[wallet].divisibility)}

    @rpc
    def getconfig(self, key, wallet=None):
        if key == "lightning":  # tell SDK we don't support lightning
            return False
        return self.config.get(key)

    @rpc(requires_network=True)
    async def getfeerate(self, multiplier=None, wallet=None):
        multiplier = float(multiplier) if multiplier else None
        return int(await self.coin.get_gas_price() * (multiplier or self.SPEED_MULTIPLIER))

    @rpc
    async def getinfo(self, wallet=None):
        path = self.get_datadir()
        is_connected = await self.coin.is_connected()
        if not is_connected:
            return {"connected": False, "path": path, "version": self.VERSION}
        numblocks = await self.coin.get_block_number()
        return {
            "blockchain_height": self.latest_height,
            "connected": is_connected,
            "gas_price": await self.getfeerate(),
            "path": path,
            "server": self.coin.current_server(),
            "server_height": numblocks,
            "spv_nodes": 0,
            "synchronized": self.synchronized,
            "total_wallets": len(self.wallets),
            "version": self.VERSION,
        }

    @rpc
    async def get_key_info(self, key, wallet=None):
        keystore = self.KEYSTORE_CLASS(key=key)
        return {
            "address": keystore.address,
            "public_key": keystore.public_key,
            "private_key": keystore.private_key,
            "seed": keystore.seed,
        }

    @rpc
    def getmasterprivate(self, *args, **kwargs):
        raise NotImplementedError(NO_MASTER_KEYS_MESSAGE)

    @rpc
    def getmerkle(self, *args, **kwargs):
        raise NotImplementedError(GET_PROOF_MESSAGE)

    @rpc
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

    @rpc(requires_wallet=True, requires_network=True)
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
        return self.SERVER

    @rpc(requires_network=True)
    @abstractmethod
    async def gettransaction(self, tx, wallet=None):
        pass

    @rpc
    def help(self, func=None, wallet=None):
        if func is None:
            return list(self.supported_methods.keys())
        if func in self.supported_methods:
            return get_function_header(func, self.supported_methods[func])
        raise Exception("Procedure not found")

    @rpc
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

    @rpc(requires_network=True)
    async def list_peers(self, wallet=None):
        return []

    @rpc(requires_wallet=True, requires_network=True)
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
            for wallet_obj in list(self.wallets.values())
            if wallet_obj.storage.path is not None
        ]

    @rpc(requires_wallet=True)
    @abstractmethod
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        pass

    @rpc
    @abstractmethod
    def make_seed(self, nbits=128, language="english", full_info=False, wallet=None):
        pass

    @rpc
    def normalizeaddress(self, address, wallet=None):
        return self.coin.normalize_address(address)

    @rpc(requires_network=True)
    @abstractmethod
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        pass

    @rpc
    async def recommended_fee(self, target=None, wallet=None):  # disable fee estimation as it's unclear what to show
        return 0

    @rpc
    def removelocaltx(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc(requires_network=True)
    async def rescan_blocks(self, start_block, end_block=None, wallet=None):
        if end_block is None:
            end_block = start_block
        start_block = int(start_block)
        end_block = int(end_block)
        await self.process_block_by_chunks(start_block, end_block)
        return True

    def restore_wallet_from_text(self, text, contract=None, path=None, address=None, **kwargs):
        if not path:
            path = os.path.join(self.get_wallet_path(), self.coin.get_wallet_key(text, contract, **kwargs))
        try:
            keystore = daemon_ctx.get().KEYSTORE_CLASS(text, contract=contract, address=address)
        except Exception as e:
            raise Exception("Invalid key provided") from e
        storage = Storage(path if path is not NOOP_PATH else None, in_memory_only=path is NOOP_PATH)
        if path is not NOOP_PATH and storage.file_exists():
            raise Exception("Remove the existing wallet first!")
        db = WalletDB("")
        db.put("keystore", keystore.dump())
        wallet_obj = self.WALLET_CLASS(self.coin, db, storage)
        wallet_obj.save_db()
        return wallet_obj

    @rpc
    def restore(self, text, wallet=None, wallet_path=None, contract=None, address=None, **kwargs):
        wallet = self.restore_wallet_from_text(text, contract, wallet_path, address=address, **kwargs)
        return {
            "path": wallet.storage.path,
            "msg": "",
        }

    @rpc(requires_wallet=True)
    def rmrequest(self, key, wallet):
        return self.wallets[wallet].remove_request(key)

    @rpc
    async def setconfig(self, key, value, wallet=None):
        if key.startswith("env_"):
            key = key[4:]
            if key in self.env_names and hasattr(self, key.upper()):
                setattr(self, key.upper(), value)
                if key in self.env_update_hooks:
                    await self.env_update_hooks[key]()
            return True
        self.config.set_config(key, value)
        return True

    @rpc(requires_wallet=True)
    def setrequestaddress(self, key, address, wallet):
        if not self.validateaddress(address):
            return False
        return bool(self.wallets[wallet].set_request_address(key, self.normalizeaddress(address)))

    @rpc(requires_wallet=True)
    @abstractmethod
    def signmessage(self, address=None, message=None, wallet=None):
        pass

    @abstractmethod
    def _sign_transaction(self, tx, private_key):
        pass

    @rpc(requires_wallet=True)
    def signtransaction(self, tx, wallet=None):
        return self._sign_transaction(tx, self.wallets[wallet].keystore.private_key)

    @rpc
    def signtransaction_with_privkey(self, tx, privkey, wallet=None):
        return self._sign_transaction(tx, privkey)

    @rpc
    def validateaddress(self, address, wallet=None):
        return self.coin.is_address(address)

    @rpc
    def validatekey(self, key, wallet=None, **kwargs):
        try:
            daemon_ctx.get().KEYSTORE_CLASS(key, **kwargs)
            return True
        except Exception:
            return False

    @rpc
    def version(self, wallet=None):
        return self.VERSION

    # token methods: fallbacks

    @rpc
    def validatecontract(self, address, wallet=None):
        return False

    @rpc
    def get_tokens(self, wallet=None):
        return {}

    @rpc
    def getabi(self, wallet=None):
        return []

    @rpc
    def debuglocks(self, wallet=None):
        locked_wallets = {}
        total_locks = 0
        for key, value in list(self.wallet_locks.items()):
            if value.locked():
                locked_wallets[key] = str(value)
                total_locks += 1
        return {"locked_wallets": locked_wallets, "total_locks": total_locks}
