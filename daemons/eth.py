import asyncio
import functools
import inspect
import json
import os
import random
import secrets
import time
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from decimal import Decimal

from aiohttp import ClientError as AsyncClientError
from base import BaseDaemon
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import PrivateKey, PublicKey
from hexbytes import HexBytes
from mnemonic import Mnemonic
from storage import ConfigDB as StorageConfigDB
from storage import JSONEncoder as StorageJSONEncoder
from storage import Storage, StoredDBProperty, StoredObject, StoredProperty
from storage import WalletDB as StorageWalletDB
from storage import decimal_to_string
from utils import (
    CastingDataclass,
    JsonResponse,
    exception_retry_middleware,
    get_exception_message,
    hide_logging_errors,
    load_json_dict,
    rpc,
    try_cast_num,
)
from web3 import Web3
from web3.contract import AsyncContract
from web3.datastructures import AttributeDict
from web3.eth import AsyncEth
from web3.exceptions import ABIFunctionNotFound, BlockNotFound
from web3.exceptions import ValidationError as Web3ValidationError
from web3.geth import AsyncGethAdmin, Geth
from web3.middleware.geth_poa import async_geth_poa_middleware
from web3.providers.rpc import get_default_http_endpoint

Account.enable_unaudited_hdwallet_features()

NO_HISTORY_MESSAGE = "We don't access transaction history to remain lightweight"
WRITE_DOWN_SEED_MESSAGE = "Please keep your seed in a safe place; if you lose it, you will not be able to restore your wallet."
ONE_ADDRESS_MESSAGE = "We only support one address per wallet as it is common in ethereum ecosystem"
GET_PROOF_MESSAGE = "Geth doesn't support get_proof correctly for now"
NO_MASTER_KEYS_MESSAGE = "As we use only one address per wallet, address keys are used, but not the xprv/xpub"

EIP1559_PARAMS = ("maxFeePerGas", "maxPriorityFeePerGas")
FEE_PARAMS = EIP1559_PARAMS + ("gasPrice", "gas")

CHUNK_SIZE = 30
AMOUNTGEN_LIMIT = 10**9

TX_DEFAULT_GAS = 21000

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

with open("daemons/abi/erc20.json") as f:
    ERC20_ABI = json.loads(f.read())

with open("daemons/tokens/erc20.json") as f:
    ERC20_TOKENS = json.loads(f.read())


class WalletDB(StorageWalletDB):
    STORAGE_VERSION = 1

    def _convert_dict(self, path, key, v):
        if key == "payment_requests":
            v = {k: Invoice(**x) for k, x in v.items()}
        if key == "used_amounts":
            v = {Decimal(k): x for k, x in v.items()}
        return v

    def _should_convert_to_stored_dict(self, key) -> bool:
        if key == "keystore":
            return False
        return True


class ConfigDB(StorageConfigDB):
    STORAGE_VERSION = 1


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


def get_wallet_key(xpub, contract=None):
    key = xpub
    if contract:
        key += f"_{contract}"
    return key


def from_wei(value: int, precision=18) -> Decimal:
    if value == 0:
        return Decimal(0)
    return Decimal(value) / Decimal(10**precision)


def to_wei(value: Decimal, precision=18) -> int:
    if value == Decimal(0):
        return 0
    return int(value * Decimal(10**precision))


async def async_http_retry_request_middleware(make_request, w3):
    return exception_retry_middleware(make_request, (AsyncClientError, TimeoutError, asyncio.TimeoutError), daemon.VERBOSE)


@dataclass
class Transaction:
    hash: str
    to: str
    value: int


@dataclass
class KeyStore:
    key: str
    address: str = None
    public_key: str = None
    private_key: str = None
    seed: str = None
    account: Account = None
    contract: str = None

    def is_watching_only(self):
        return self.private_key is None

    def load_contract(self):
        if not self.contract:
            return
        try:
            self.contract = Web3.toChecksumAddress(self.contract)
        except Exception:
            raise Exception("Error loading wallet: invalid address")

    def __post_init__(self):
        self.load_contract()
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
        return cls(key=db.get("key", ""), contract=db.get("contract", None))

    def dump(self):
        return {"key": self.key, "contract": self.contract}


@dataclass
class Invoice(CastingDataclass, StoredObject):
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
    contract: str = None

    @property
    def status_str(self):
        status_str = pr_tooltips[self.status]
        if self.status == PR_UNPAID:
            if self.exp > 0:
                expiration = self.exp + self.time
                status_str = "Expires at " + time.ctime(expiration)
        return status_str


async def get_balance(web3, address):
    return from_wei(await web3.eth.get_balance(address))


@dataclass
class Wallet:
    web3: Web3
    db: WalletDB
    storage: Storage
    keystore: KeyStore = field(init=False)
    used_amounts: dict = field(default_factory=dict)
    receive_requests: dict = field(default_factory=dict)
    contract: str = None
    symbol: str = None
    divisibility: int = 18
    _token_fetched = False

    latest_height = StoredDBProperty("latest_height", -1)

    def __post_init__(self):
        if self.symbol is None:
            self.symbol = daemon.name
        self.keystore = KeyStore.load(self.db.get("keystore"))
        self.receive_requests = self.db.get_dict("payment_requests")
        self.used_amounts = self.db.get_dict("used_amounts")
        self.running = False
        self.loop = asyncio.get_event_loop()
        self.synchronized = False

    def save_db(self):
        if self.storage:
            self.db.write(self.storage)

    async def fetch_token_info(self):
        self.symbol = (await daemon.readcontract(self.contract, "symbol")).upper()
        self.divisibility = await daemon.readcontract(self.contract, "decimals")
        self._token_fetched = True

    async def start(self, blocks):
        if self.latest_height == -1:
            self.latest_height = await self.web3.eth.block_number
        if self.contract and not self._token_fetched:
            await self.fetch_token_info()

        self.running = True
        # process onchain transactions
        for block in blocks:
            for tx in block:
                await process_transaction(tx)
        current_height = await self.web3.eth.block_number
        if self.contract:
            # process token transactions
            await check_contract_logs(
                self.contract,
                self.divisibility,
                from_block=self.latest_height + 1,
                to_block=min(self.latest_height + daemon.MAX_SYNC_BLOCKS, current_height),
            )
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
        self.used_amounts.clear()
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

    async def balance(self):
        if self.contract:
            return from_wei(await daemon.readcontract(self.contract, "balanceOf", self.address), self.divisibility)
        return await get_balance(self.web3, self.address)

    def stop(self, block_number):
        self.running = False
        self.latest_height = block_number

    async def make_payment_request(self, address, amount, message, expiration):
        amount = amount or Decimal()
        if amount < 0:
            raise Exception("Out of bounds amount")
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
        divisibility = min(self.divisibility, daemon.AMOUNTGEN_DIVISIBILITY)
        AMOUNTGEN_PRECISION = Decimal(10) ** (-divisibility)
        while cur_amount in self.used_amounts:
            cur_amount = amount + random.randint(add_low, add_high) * AMOUNTGEN_PRECISION
            if add_high < AMOUNTGEN_LIMIT:
                add_low = add_high + 1
                add_high *= 2
        return cur_amount

    def add_payment_request(self, req, save_db=True):
        self.receive_requests[req.id] = req
        self.used_amounts[req.amount] = req.id
        if save_db:
            self.save_db()
        return req

    async def get_request_url(self, req):
        chain_id = await self.web3.eth.chain_id
        amount_wei = to_wei(req.amount, self.divisibility)
        if self.contract:
            return f"ethereum:{self.contract.address}@{chain_id}/transfer?address={req.address}&uint256={amount_wei}"
        return f"ethereum:{req.address}@{chain_id}?value={amount_wei}"

    async def export_request(self, req):
        d = {
            "id": req.id,
            "is_lightning": False,
            f"amount_{self.symbol}": decimal_to_string(req.amount, self.divisibility),
            "message": req.message,
            "timestamp": req.time,
            "expiration": req.time + req.exp if req.exp else 0,
            "status": req.status,
            "status_str": req.status_str,
        }
        if req.tx_hash:
            d["tx_hash"] = req.tx_hash
            d["contract"] = req.contract
            d["confirmations"] = (
                await self.web3.eth.block_number
                - (await self.web3.eth.get_transaction_receipt(req.tx_hash))["blockNumber"]
                + 1
            )
        d["amount_wei"] = to_wei(req.amount, self.divisibility)
        d["address"] = req.address
        d["URI"] = await self.get_request_url(req)
        return d

    def get_request(self, key):
        try:
            amount = Decimal(key)
            key = self.used_amounts.get(amount)
        finally:
            return self.receive_requests.get(key)

    def remove_request(self, key):
        req = self.get_request(key)
        if not req:
            return False
        self.used_amounts.pop(req.amount, None)
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
        if req.status == PR_PAID:  # immutable
            return req
        req.status = status
        for kwarg in kwargs:
            setattr(req, kwarg, kwargs[kwarg])
        self.add_payment_request(req, save_db=False)
        if status != PR_UNPAID:
            self.used_amounts.pop(req.amount, None)
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

    async def process_payment(self, wallet, amount, tx_hash, contract=None):
        try:
            req = self.set_request_status(amount, PR_PAID, tx_hash=tx_hash, contract=contract)
            await daemon.trigger_event(
                {
                    "event": "new_payment",
                    "address": req.id,
                    "status": req.status,
                    "status_str": req.status_str,
                    "contract": contract,
                },
                wallet,
            )
        except Exception:
            if daemon.VERBOSE:
                print(f"Error processing successful payment {tx_hash} with {amount}:")
                print(traceback.format_exc())


async def process_transaction(tx, contract=None, divisibility=18):
    to = tx.to
    amount = from_wei(tx.value, divisibility)
    if to not in daemon.addresses:
        return
    for wallet in daemon.addresses[to]:
        wallet_contract = daemon.wallets[wallet].contract.address if daemon.wallets[wallet].contract else None
        if contract != wallet_contract:
            continue
        await daemon.trigger_event({"event": "new_transaction", "tx": tx.hash}, wallet)
        if amount in daemon.wallets[wallet].used_amounts:
            daemon.loop.create_task(daemon.wallets[wallet].process_payment(wallet, amount, tx.hash, contract))


async def check_contract_logs(contract, divisibility, from_block=None, to_block=None):
    try:
        for tx_data in await contract.events.Transfer.getLogs(fromBlock=from_block, toBlock=to_block):
            try:
                tx = Transaction(str(tx_data["transactionHash"].hex()), tx_data["args"]["to"], tx_data["args"]["value"])
                await process_transaction(tx, contract.address, divisibility)
            except Exception:
                if daemon.VERBOSE:
                    print(f"Error processing transaction {tx_data['transactionHash'].hex()}:")
                    print(traceback.format_exc())
    except Exception:
        if daemon.VERBOSE:
            print(f"Error getting logs on contract {contract.address}:")
            print(traceback.format_exc())


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
        "getaddressbalance_wallet": "getaddressbalance",
        "getunusedaddress": "getaddress",
        "list_invoices": "list_requests",
    }
    SKIP_NETWORK = ["getinfo", "exchange_rate", "list_currencies"]

    VERSION = "4.1.5"  # version of electrum API with which we are "compatible"
    BLOCK_TIME = 5
    FX_FETCH_TIME = 150
    ABI = ERC20_ABI
    TOKENS = ERC20_TOKENS
    # modern transactions with maxPriorityFeePerGas
    EIP1559_SUPPORTED = True
    DEFAULT_MAX_SYNC_BLOCKS = 300  # (60/12)=5*60 (a block every 12 seconds, max normal expiry time 60 minutes)
    # from coingecko API
    FIAT_NAME = "ethereum"
    # Max number of decimal places to use for amounts generation
    AMOUNTGEN_DIVISIBILITY = 8

    latest_height = StoredProperty("latest_height", -1)

    def __init__(self):
        super().__init__()
        if not hasattr(self, "CONTRACT_FIAT_NAME"):
            self.CONTRACT_FIAT_NAME = self.FIAT_NAME
        self.exchange_rates = defaultdict(dict)
        self.contracts = {}
        self.latest_blocks = deque(maxlen=self.MAX_SYNC_BLOCKS)
        self.config_path = os.path.join(self.get_datadir(), "config")
        self.config = ConfigDB(self.config_path)
        self.contract_heights = self.config.get_dict("contract_heights")
        self.web3 = Web3(
            Web3.AsyncHTTPProvider(self.SERVER, request_kwargs={"timeout": 5 * 60}),
            modules={
                "eth": (AsyncEth,),
                "geth": (Geth, {"admin": (AsyncGethAdmin,)}),
            },
            middlewares=[],
        )
        self.web3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
        self.web3.middleware_onion.inject(async_http_retry_request_middleware, layer=0)
        self.get_block_safe = exception_retry_middleware(self.web3.eth.get_block, (BlockNotFound,), self.VERBOSE)
        # initialize wallet storages
        self.wallets = {}
        self.addresses = defaultdict(set)
        self.wallets_updates = {}
        # initialize not yet created network
        self.running = True
        self.loop = None
        self.synchronized = False

    def load_env(self):
        super().load_env()
        self.SERVER = self.env("SERVER", default=get_default_http_endpoint())
        max_sync_hours = self.env("MAX_SYNC_HOURS", cast=int, default=1)
        self.MAX_SYNC_BLOCKS = max_sync_hours * self.DEFAULT_MAX_SYNC_BLOCKS

    async def on_startup(self, app):
        await super().on_startup(app)
        self.loop = asyncio.get_event_loop()
        if self.latest_height == -1:
            self.latest_height = await self.web3.eth.block_number
        self.loop.create_task(self.process_pending())
        self.loop.create_task(self.fetch_exchange_rates())

    async def get_rates(self, contract=None):
        url = (
            f"https://api.coingecko.com/api/v3/coins/{self.FIAT_NAME}?localization=false&sparkline=false"
            if not contract
            else f"https://api.coingecko.com/api/v3/coins/{self.CONTRACT_FIAT_NAME}/contract/{contract.lower()}"
        )
        async with self.client_session.get(url) as response:
            got = await response.json()
        prices = got["market_data"]["current_price"]
        return {price[0].upper(): Decimal(str(price[1])) for price in prices.items()}

    async def fetch_exchange_rates(self, currency=None, contract=None):
        if currency is None:
            currency = self.name
        while self.running:
            try:
                self.exchange_rates[currency] = await self.get_rates(contract)
            except Exception:
                if self.VERBOSE:
                    print(f"Error fetching exchange rates for {currency}:")
                    print(traceback.format_exc())
            await asyncio.sleep(self.FX_FETCH_TIME)

    async def process_block(self, start_height, end_height):
        for block_number in range(start_height, end_height + 1):
            try:
                await self.trigger_event({"event": "new_block", "height": block_number}, None)
                block = (await self.get_block_safe(block_number, full_transactions=True))["transactions"]
                transactions = []
                for tx_data in block:
                    try:
                        tx = Transaction(str(tx_data["hash"].hex()), tx_data["to"], tx_data["value"])
                        transactions.append(tx)
                        await process_transaction(tx)
                    except Exception:
                        if self.VERBOSE:
                            print(f"Error processing transaction {tx_data['hash'].hex()}:")
                            print(traceback.format_exc())
                self.latest_blocks.append(transactions)
            except Exception:
                if self.VERBOSE:
                    print(f"Error processing block {block_number}:")
                    print(traceback.format_exc())

    async def process_pending(self):
        while self.running:
            try:
                current_height = await self.web3.eth.block_number
                tasks = []
                # process at max 300 blocks since last processed block, fetched by chunks
                for block_number in range(
                    self.latest_height + 1, min(self.latest_height + self.MAX_SYNC_BLOCKS, current_height) + 1, CHUNK_SIZE
                ):
                    tasks.append(self.process_block(block_number, min(block_number + CHUNK_SIZE - 1, current_height)))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                if self.VERBOSE:
                    for task in results:
                        if isinstance(task, Exception):
                            print(get_exception_traceback(task))
                self.latest_height = current_height
                self.synchronized = True  # set it once, as we just need to ensure initial sync was done
            except Exception:
                if self.VERBOSE:
                    print("Error processing pending blocks:")
                    print(traceback.format_exc())
            await asyncio.sleep(self.BLOCK_TIME)

    async def add_contract(self, contract, wallet):
        if not contract:
            return
        contract = Web3.toChecksumAddress(contract)
        if contract in self.contracts:
            self.wallets[wallet].contract = self.contracts[contract]
            return
        if contract not in self.contract_heights:
            self.contract_heights[contract] = await self.web3.eth.block_number
        self.contracts[contract] = await self.start_contract_listening(contract)
        self.wallets[wallet].contract = self.contracts[contract]
        await self.wallets[wallet].fetch_token_info()
        self.loop.create_task(self.fetch_exchange_rates(self.wallets[wallet].symbol, contract))

    async def start_contract_listening(self, contract):
        contract_obj = self.create_web3_contract(contract)
        divisibility = await self.readcontract(contract_obj, "decimals")
        self.loop.create_task(self.check_contracts(contract_obj, divisibility))
        return contract_obj

    def create_web3_contract(self, contract):
        try:
            return self.web3.eth.contract(address=contract, abi=self.ABI)
        except Exception as e:
            raise Exception("Invalid contract address or non-ERC20 token") from e

    async def check_contracts(self, contract, divisibility):
        while self.running:
            try:
                current_height = await self.web3.eth.block_number
                if current_height > self.contract_heights[contract.address]:
                    await check_contract_logs(
                        contract,
                        divisibility,
                        from_block=self.contract_heights[contract.address] + 1,
                        to_block=min(self.contract_heights[contract.address] + daemon.MAX_SYNC_BLOCKS, current_height),
                    )
                    self.contract_heights[contract.address] = current_height
            except Exception:
                if self.VERBOSE:
                    print("Error processing contract logs:")
                    print(traceback.format_exc())
            await asyncio.sleep(self.BLOCK_TIME)

    async def trigger_event(self, data, wallet):
        for key in self.wallets:
            if not wallet or wallet == key:
                await self.notify_websockets(data, key)
                self.wallets_updates[key].append(data)

    async def on_shutdown(self, app):
        self.running = False
        block_number = await self.web3.eth.block_number
        for wallet in self.wallets.values():
            wallet.stop(block_number)
        await super().on_shutdown(app)

    def get_method_data(self, method):
        return self.supported_methods[method]

    def get_exception_message(self, e):
        return get_exception_message(e)

    def user_dir(self):
        if os.name == "posix":
            return os.path.join(os.environ["HOME"], f".bitcart-{self.name.lower()}")
        elif "APPDATA" in os.environ:
            return os.path.join(os.environ["APPDATA"], f"Bitcart-{self.name.upper()}")
        elif "LOCALAPPDATA" in os.environ:
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

    async def load_wallet(self, xpub, contract):
        wallet_key = get_wallet_key(xpub, contract)
        if wallet_key in self.wallets:
            await self.add_contract(contract, wallet_key)
            return self.wallets[wallet_key]
        if not xpub:
            return None

        # get wallet on disk
        wallet_dir = self.get_wallet_path()
        wallet_path = os.path.join(wallet_dir, wallet_key)
        if not os.path.exists(wallet_path):
            self.restore(xpub, wallet_path=wallet_path, contract=contract)
        storage = Storage(wallet_path)
        db = WalletDB(storage.read())
        wallet = Wallet(self.web3, db, storage)
        self.wallets[wallet_key] = wallet
        self.wallets_updates[wallet_key] = []
        self.addresses[wallet.address].add(wallet_key)
        await self.add_contract(contract, wallet_key)
        await wallet.start(self.latest_blocks.copy())
        return wallet

    async def is_still_syncing(self, wallet=None):
        return not await self.web3.isConnected() or await self.web3.eth.syncing or (wallet and not wallet.is_synchronized())

    async def _get_wallet(self, id, req_method, xpub, contract):
        wallet = error = None
        try:
            should_skip = req_method not in self.supported_methods or not self.supported_methods[req_method].requires_network
            while not should_skip and not self.synchronized:  # wait for initial sync to fetch blocks
                await asyncio.sleep(0.1)
            wallet = await self.load_wallet(xpub, contract)
            if should_skip:
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

    async def execute_method(self, id, req_method, xpub, contract, req_args, req_kwargs):
        wallet, error = await self._get_wallet(id, req_method, xpub, contract)
        if error:
            return error.send()
        exec_method, error = await self.get_exec_method(id, req_method)
        if error:
            return error.send()
        if self.get_method_data(req_method).requires_wallet and not xpub:
            return JsonResponse(code=-32000, error="Wallet not loaded", id=id).send()
        try:
            result = await self.get_exec_result(get_wallet_key(xpub, contract), req_args, req_kwargs, exec_method)
            return JsonResponse(result=result, id=id).send()
        except BaseException as e:
            if self.VERBOSE:
                print(traceback.format_exc())
            error_message = self.get_exception_message(e)
            return JsonResponse(code=self.get_error_code(error_message), error=error_message, id=id).send()

    ### Methods ###

    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        await self.web3.geth.admin.add_peer(url)

    @rpc(requires_wallet=True, requires_network=True)
    async def add_request(self, amount, memo="", expiration=3600, force=False, wallet=None):
        amount = Decimal(amount)
        addr = self.wallets[wallet].address
        expiration = int(expiration) if expiration else None
        req = await self.wallets[wallet].make_payment_request(addr, amount, memo, expiration)
        self.wallets[wallet].add_payment_request(req)
        self.loop.create_task(self.wallets[wallet].expired_task(req))
        return await self.wallets[wallet].export_request(req)

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        return to_dict(await self.web3.eth.send_raw_transaction(tx))

    @rpc(requires_wallet=True)
    def clear_requests(self, wallet):
        self.wallets[wallet].clear_requests()
        return True

    @rpc(requires_wallet=True, requires_network=True)
    async def close_wallet(self, wallet):
        block_number = await self.web3.eth.block_number
        self.wallets[wallet].stop(block_number)
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

    @rpc
    async def createnewaddress(self, *args, **kwargs):
        raise NotImplementedError(ONE_ADDRESS_MESSAGE)

    @rpc
    def exchange_rate(self, currency=None, wallet=None):
        origin_currency = self.wallets[wallet].symbol if wallet else self.name
        if not currency:
            currency = self.DEFAULT_CURRENCY
        return str(self.exchange_rates[origin_currency].get(currency, Decimal("NaN")))

    @rpc(requires_network=True)
    async def get_default_gas(self, tx, wallet=None):
        tx_dict = load_json_dict(tx, "Invalid transaction").copy()
        tx_dict.pop("chainId", None)
        for param in FEE_PARAMS:
            tx_dict.pop(param, None)
        return await self.web3.eth.estimate_gas(tx_dict)

    @rpc(requires_network=True)
    async def get_default_fee(self, tx, wallet=None):
        tx_dict = load_json_dict(tx, "Invalid transaction")
        has_modern_params = any(v in tx_dict for v in EIP1559_PARAMS)
        has_legacy_params = "gasPrice" in tx_dict
        if (
            (has_modern_params and has_legacy_params)
            or (has_modern_params and not self.EIP1559_SUPPORTED)
            or "gas" not in tx_dict
        ):
            raise Exception("Invalid mix of transaction fee params")
        if has_modern_params:
            base_fee = (await self.web3.eth.get_block("latest")).baseFeePerGas
            fee = (from_wei(tx_dict["maxPriorityFeePerGas"]) + from_wei(base_fee)) * tx_dict["gas"]
        else:
            fee = from_wei(tx_dict["gasPrice"]) * tx_dict["gas"]
        return to_dict(fee)

    @rpc
    def get_tokens(self, wallet=None):
        return self.TOKENS

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        return to_dict(Web3.keccak(hexstr=tx_data))

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        return len(Web3.toBytes(hexstr=tx_data))

    @rpc(requires_network=True)
    async def get_tx_status(self, tx, wallet=None):
        data = to_dict(await self.web3.eth.get_transaction_receipt(tx))
        data["confirmations"] = max(0, await self.web3.eth.block_number - data["blockNumber"] + 1)
        return data

    @rpc(requires_wallet=True, requires_network=True)
    def get_updates(self, wallet):
        updates = self.wallets_updates[wallet]
        self.wallets_updates[wallet] = []
        return updates

    @rpc
    def getabi(self, wallet=None):
        return self.ABI

    @rpc(requires_wallet=True)
    def getaddress(self, wallet):
        return self.wallets[wallet].address

    @rpc(requires_network=True)
    async def getaddressbalance(self, address, wallet=None):
        return to_dict(await get_balance(self.web3, address))

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
    async def getfeerate(self, wallet=None):
        return await self.web3.eth.gas_price

    @rpc
    async def getinfo(self, wallet=None):
        path = self.get_datadir()
        if not await self.web3.isConnected():
            return {"connected": False, "path": path, "version": self.VERSION}
        try:
            nodes = len(await self.web3.geth.admin.peers())
        except Exception:
            nodes = 0
        numblocks = await self.web3.eth.block_number
        return {
            "blockchain_height": numblocks,
            "connected": await self.web3.isConnected(),
            "gas_price": await self.web3.eth.gas_price,
            "path": path,
            "server": self.SERVER,
            "server_height": numblocks,
            "spv_nodes": nodes,
            "synchronized": not await self.web3.eth.syncing and self.synchronized,
            "version": self.VERSION,
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
        return [self.SERVER]

    @rpc(requires_network=True)
    async def gettransaction(self, tx, wallet=None):
        data = to_dict(await self.web3.eth.get_transaction(tx))
        data["confirmations"] = max(0, await self.web3.eth.block_number - data["blockNumber"] + 1)
        return data

    @rpc
    def help(self, wallet=None):
        return list(self.supported_methods.keys())

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

    @rpc
    def list_currencies(self, wallet=None):
        origin_currency = self.wallets[wallet].symbol if wallet else self.name
        return list(self.exchange_rates[origin_currency].keys())

    @rpc(requires_network=True)
    async def list_peers(self, wallet=None):
        return to_dict(await self.web3.geth.admin.peers())

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
            for wallet_obj in self.wallets.values()
        ]

    @rpc(requires_wallet=True)
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        unused, funded, balance = str_to_bool(unused), str_to_bool(funded), str_to_bool(balance)
        address = self.wallets[wallet].address
        addr_balance = await get_balance(self.web3, address)
        ntxs = await self.web3.eth.get_transaction_count(address)
        if (unused and (addr_balance > 0 or ntxs > 0)) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, to_dict(addr_balance))]
        else:
            return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", wallet=None):
        return Mnemonic(language).generate(nbits)

    @rpc
    def normalizeaddress(self, address, wallet=None):
        return Web3.toChecksumAddress(address)

    async def get_common_payto_params(self, address):
        nonce = await self.web3.eth.get_transaction_count(address, block_identifier="pending")
        return {
            "nonce": nonce,
            "chainId": await self.web3.eth.chain_id,
            "from": address,
            **(await self.get_fee_params()),
        }

    @rpc(requires_wallet=True, requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        address = self.wallets[wallet].address
        tx_dict = {
            "to": destination,
            "value": Web3.toWei(amount, "ether"),
            **(await self.get_common_payto_params(address)),
        }
        if self.EIP1559_SUPPORTED:
            tx_dict["type"] = "0x2"
        if fee:
            tx_dict["maxFeePerGas"] = Web3.toWei(fee, "ether")
        if feerate:
            tx_dict["maxPriorityFeePerGas"] = Web3.toWei(feerate, "gwei")
        tx_dict["gas"] = int(gas) if gas else await self.get_default_gas(tx_dict)
        if unsigned:
            return tx_dict
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        return self._sign_transaction(tx_dict, self.wallets[wallet].keystore.private_key)

    async def get_fee_params(self):
        if self.EIP1559_SUPPORTED:
            block = await self.web3.eth.get_block("latest")
            max_priority_fee = await self.web3.eth.max_priority_fee
            max_fee = block.baseFeePerGas * 2 + max_priority_fee
            return {"maxFeePerGas": max_fee, "maxPriorityFeePerGas": max_priority_fee}
        gas_price = await self.web3.eth.gas_price
        return {"gasPrice": gas_price}

    def load_contract_exec_function(self, address, function, *args, **kwargs):
        kwargs.pop("wallet", None)
        if isinstance(address, AsyncContract):
            contract = address
        else:
            try:
                address = Web3.toChecksumAddress(address)
            except Exception as e:
                raise Exception("Invalid address") from e
            contract = self.create_web3_contract(address)
        # try converting args to int if possible
        args = [try_cast_num(x) for x in args]
        kwargs = {k: try_cast_num(v) for k, v in kwargs.items()}
        try:
            exec_function = getattr(contract.functions, function)
        except ABIFunctionNotFound as e:
            raise Exception(f"Contract ABI is missing {function} function") from e
        try:
            exec_function = exec_function(*args, **kwargs)
        except Web3ValidationError as e:
            raise Exception(f"Invalid arguments for {function} function") from e
        return exec_function

    @rpc(requires_network=True)
    async def readcontract(self, address, function, *args, **kwargs):
        exec_function = self.load_contract_exec_function(address, function, *args, **kwargs)
        return await exec_function.call()

    @rpc
    async def recommended_fee(self, target=None, wallet=None):  # disable fee estimation as it's unclear what to show
        return 0

    @rpc
    def removelocaltx(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc
    def restore(self, text, wallet=None, wallet_path=None, contract=None):
        if not wallet_path:
            wallet_path = os.path.join(self.get_wallet_path(), text)
        try:
            keystore = KeyStore(text, contract=contract)
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

    @rpc
    def setconfig(self, key, value, wallet=None):
        self.config.set_config(key, value)
        return True

    @rpc(requires_wallet=True)
    def signmessage(self, address=None, message=None, wallet=None):
        # Mimic electrum API
        if not address and not message:
            raise ValueError("No message specified")
        if not message:
            message = address
        return to_dict(Account.sign_message(encode_defunct(text=message), private_key=self.wallets[wallet].key).signature)

    def _sign_transaction(self, tx, private_key):
        if private_key is None:
            raise Exception("This is a watching-only wallet")
        tx_dict = load_json_dict(tx, "Invalid transaction")
        return to_dict(Account.sign_transaction(tx_dict, private_key=private_key).rawTransaction)

    @rpc(requires_wallet=True)
    def signtransaction(self, tx, wallet=None):
        return self._sign_transaction(tx, self.wallets[wallet].keystore.private_key)

    @rpc
    def signtransaction_with_privkey(self, tx, privkey, wallet=None):
        return self._sign_transaction(tx, privkey)

    @rpc(requires_wallet=True, requires_network=True)
    async def transfer(self, address, to, value, gas=None, unsigned=False, wallet=None):
        try:
            divisibility = await self.readcontract(address, "decimals")
            value = to_wei(Decimal(value), divisibility)
        except Exception:
            raise Exception("Invalid arguments for transfer function")
        return await self.writecontract(address, "transfer", to, value, gas=gas, unsigned=unsigned, wallet=wallet)

    @rpc
    def validateaddress(self, address, wallet=None):
        return is_address(address)

    @rpc
    def validatecontract(self, address, wallet=None):
        try:
            self.create_web3_contract(Web3.toChecksumAddress(address))
            return True
        except Exception:
            return False

    @rpc
    def validatekey(self, key, wallet=None):
        try:
            KeyStore(key)
            return True
        except Exception:
            return False

    @rpc
    def verifymessage(self, address, signature, message, wallet=None):
        return Web3.toChecksumAddress(
            Account.recover_message(encode_defunct(text=message), signature=signature)
        ) == Web3.toChecksumAddress(address)

    @rpc
    def version(self, wallet=None):
        return self.VERSION

    @rpc(requires_wallet=True, requires_network=True)
    async def writecontract(self, address, function, *args, **kwargs):
        wallet = kwargs.pop("wallet")
        unsigned = kwargs.pop("unsigned", False)
        gas = kwargs.pop("gas", None)
        exec_function = self.load_contract_exec_function(address, function, *args, **kwargs)
        # pass gas here to avoid calling estimate_gas on an incomplete tx
        tx = await exec_function.build_transaction(
            {**await self.get_common_payto_params(self.wallets[wallet].address), "gas": TX_DEFAULT_GAS}
        )
        tx["gas"] = int(gas) if gas else await self.get_default_gas(tx)
        if unsigned:
            return tx
        signed = self._sign_transaction(tx, self.wallets[wallet].keystore.private_key)
        return await self.broadcast(signed)


if __name__ == "__main__":
    daemon = ETHDaemon()
    daemon.start()
