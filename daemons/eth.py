import asyncio
import functools
import inspect
import json
import time
import traceback
from dataclasses import dataclass, field
from decimal import Decimal

from base import BaseDaemon
from eth_account import Account
from eth_keys.datatypes import PublicKey
from hexbytes import HexBytes
from mnemonic import Mnemonic
from utils import JsonResponse, get_exception_message, hide_logging_errors, periodic_task, rpc
from web3 import Web3
from web3.datastructures import AttributeDict
from web3.eth import AsyncEth
from web3.geth import AsyncGethAdmin, Geth
from web3.providers.rpc import get_default_http_endpoint

Account.enable_unaudited_hdwallet_features()

NO_HISTORY_MESSAGE = "We don't access transaction history to remain lightweight"
WRITE_DOWN_SEED_MESSAGE = "Please keep your seed in a safe place; if you lose it, you will not be able to restore your wallet."

CHUNK_SIZE = 30
# TODO: limit sync post-reboot to (60/12)*60=5*60=300 blocks (max expiry time)


@dataclass
class Address:
    address: str
    balance: Decimal = 0


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, AttributeDict):
            return {k: v for k, v in obj.items()}
        if isinstance(obj, HexBytes):
            return str(obj.hex())
        return super().default(obj)


def to_dict(obj):
    return json.loads(json.dumps(obj, cls=JSONEncoder))


@dataclass
class Wallet:
    key: str
    web3: Web3
    BLOCK_TIME: int = 5
    ADDRESS_CHECK_TIME: int = 60
    address: str = None
    path: str = ""
    updates: dict = field(default_factory=dict)
    invoices: dict = field(default_factory=dict)
    pending_invoices: dict = field(default_factory=dict)

    def __post_init__(self):
        try:
            self.address = Account.from_mnemonic(self.key).address
        except Exception:
            try:
                self.address = Account.from_key(self.key).address
            except Exception:
                try:
                    self.address = PublicKey.from_compressed_bytes(Web3.toBytes(hexstr=self.key)).to_checksum_address()
                except Exception:
                    if not Web3.isAddress(self.key) and not Web3.isChecksumAddress(self.key):
                        raise Exception("Error loading wallet: invalid address")
                    self.address = Web3.toChecksumAddress(self.key)
        self.running = False
        self.loop = asyncio.get_event_loop()

    def start(self):
        self.running = True
        self.loop.create_task(periodic_task(self, self.process_pending, self.BLOCK_TIME))

    async def process_pending(self):
        if not self.pending_invoices:
            return
        for address in self.pending_invoices:
            print(await self.web3.eth.get_balance(address))

    def is_synchronized(self):  # because only one address is used due to eth specifics
        return True

    async def balance(self):
        return await self.web3.eth.get_balance(self.address)

    def stop(self):
        self.running = False


class ETHDaemon(BaseDaemon):
    name = "ETH"
    BASE_SPEC_FILE = "daemons/spec/eth.json"
    DEFAULT_PORT = 5002
    ALIASES = {"commands": "help", "clear_invoices": "clear_requests"}
    SKIP_NETWORK = ["getinfo"]

    VERSION = "4.1.5"  # version of electrum API with which we are "compatible"
    BLOCK_TIME = 5
    ADDRESS_CHECK_TIME = 60

    def __init__(self):
        super().__init__()
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
        self.wallets_updates = {}
        # initialize not yet created network
        self.running = True
        self.loop = None

    def load_env(self):
        super().load_env()
        self.DATA_PATH = self.config("DATA_PATH", default=None)
        self.NET = self.config("NETWORK", default="mainnet")
        self.VERBOSE = self.config("DEBUG", cast=bool, default=False)
        self.HTTP_HOST = self.config("HTTP_HOST", default=get_default_http_endpoint())

    async def on_startup(self, app):
        self.loop = asyncio.get_event_loop()
        self.latest_height = await self.web3.eth.block_number
        self.loop.create_task(self.process_pending())
        await super().on_startup(app)

    async def process_block(self, start_height, end_height):
        for block_number in range(start_height, end_height + 1):
            for tx in (await self.web3.eth.get_block(block_number, full_transactions=True))["transactions"]:
                pass

    async def process_pending(self):
        while self.running:
            current_height = await self.web3.eth.block_number
            tasks = []
            for block_number in range(self.latest_height + 1, current_height + 1, CHUNK_SIZE):
                tasks.append(self.process_block(block_number, min(block_number + CHUNK_SIZE - 1, current_height)))
            await asyncio.gather(*tasks)
            self.latest_height = current_height
            await asyncio.sleep(self.BLOCK_TIME)

    async def on_shutdown(self, app):
        self.running = False
        for wallet in self.wallets.values():
            wallet.stop()
        await super().on_shutdown(app)

    async def maintain_network(self):
        while self.running:
            start = time.time()
            try:
                await self.process_pending()
            except Exception:
                if self.VERBOSE:
                    print(traceback.format_exc())
            elapsed = time.time() - start
            await asyncio.sleep(max(self.BLOCK_TIME - elapsed, 0))

    async def maintain_addresses(self):
        while self.running:
            start = time.time()
            try:
                await self.process_addresses()
            except Exception:
                if self.VERBOSE:
                    print(traceback.format_exc())
            elapsed = time.time() - start
            await asyncio.sleep(max(self.ADDRESS_CHECK_TIME - elapsed, 0))

    def get_method_data(self, method):
        return self.supported_methods[method]

    def get_exception_message(self, e):
        return get_exception_message(e)

    async def load_wallet(self, xpub):
        if xpub in self.wallets:
            return self.wallets[xpub]
        if not xpub:
            return None

        wallet = Wallet(xpub, self.web3, self.BLOCK_TIME, self.ADDRESS_CHECK_TIME)
        wallet.start()
        self.wallets[xpub] = wallet
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

    async def get_exec_result(self, xpub, req_args, req_kwargs, exec_method, **kwargs):
        # wallet = kwargs.pop("wallet", None)
        exec_method = functools.partial(exec_method, wallet=xpub)
        with hide_logging_errors(not self.VERBOSE):
            result = exec_method(*req_args, **req_kwargs)
            return await result if inspect.isawaitable(result) else result

    async def execute_method(self, id, req_method, req_args, req_kwargs):
        # self.pending_invoices[Web3.toChecksumAddress(req_args[0])] = {}
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
            result = await self.get_exec_result(xpub, req_args, req_kwargs, exec_method, wallet=wallet)
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

    @rpc
    async def broadcast(self, tx, wallet=None):
        return await self.web3.eth.send_raw_transaction(tx)

    @rpc(requires_wallet=True)
    def clear_requests(self, wallet):
        self.wallets[wallet].invoices = {}
        self.wallets[wallet].pending_invoices = {}
        return True

    @rpc
    async def create(self, wallet=None):
        seed = self.make_seed()
        wallet = Wallet(seed, self.web3, self.BLOCK_TIME, self.ADDRESS_CHECK_TIME)
        return {
            "seed": seed,
            "path": wallet.path,  # TODO: add
            "msg": WRITE_DOWN_SEED_MESSAGE,
        }

    @rpc
    async def get_tx_status(self, tx, wallet=None):
        data = to_dict(await self.web3.eth.get_transaction_receipt(tx))
        data["confirmations"] = max(0, (await self.web3.eth.block_number) - data["blockNumber"])
        return data

    @rpc
    async def getaddressbalance(self, address, wallet=None):
        return await self.web3.eth.get_balance(address)

    @rpc
    def getaddresshistory(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc(requires_wallet=True)
    async def getbalance(self, wallet):
        return await self.wallets[wallet].balance()

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
            "path": "",  # TODO: add
            "server": self.HTTP_HOST,
            "server_height": numblocks,
            "spv_nodes": len(await self.web3.geth.admin.peers()),
            "version": self.VERSION,
        }

    @rpc
    def getmerkle(self, *args, **kwargs):
        raise NotImplementedError("Geth doesn't support get_proof correctly for now")

    @rpc
    def getservers(self, wallet=None):
        return [self.HTTP_HOST]

    @rpc
    def help(self, wallet=None):
        return list(self.supported_methods.keys())

    @rpc(requires_wallet=True)
    def ismine(self, address, wallet):
        return address == self.wallets[wallet].address

    @rpc
    async def list_peers(self, wallet=None):
        return to_dict(await self.web3.geth.admin.peers())

    @rpc
    def list_wallets(self, wallet=None):
        return [
            {"path": "", "synchronized": wallet_obj.is_synchronized()} for wallet_obj in self.wallets.values()
        ]  # TODO: add path

    @rpc
    def make_seed(self, nbits=128, language="english", wallet=None):
        return Mnemonic(language).generate(nbits)

    @rpc
    def validateaddress(self, address, wallet=None):
        return Web3.isAddress(address) or Web3.isChecksumAddress(address)

    @rpc
    def version(self, wallet=None):
        return self.VERSION


if __name__ == "__main__":
    daemon = ETHDaemon()
    daemon.start()
