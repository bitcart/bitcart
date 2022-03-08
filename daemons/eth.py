import asyncio
import functools
import inspect
import json
import threading
import time
import traceback
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List

from base import BaseDaemon
from eth_keys.datatypes import PublicKey
from hexbytes import HexBytes
from mnemonic import Mnemonic
from pycoin.symbols.btc import network as bitcoin_network
from utils import JsonResponse, get_exception_message, hide_logging_errors, periodic_task, rpc
from web3 import Web3
from web3.datastructures import AttributeDict
from web3.providers.ipc import IPCProvider, get_default_ipc_path

NO_HISTORY_MESSAGE = "We don't access transaction history to remain lightweight"
WRITE_DOWN_SEED_MESSAGE = "Please keep your seed in a safe place; if you lose it, you will not be able to restore your wallet."


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
    path: str = ""
    addresses: List[str] = field(default_factory=list)
    updates: dict = field(default_factory=dict)
    invoices: dict = field(default_factory=dict)
    pending_invoices: dict = field(default_factory=dict)
    gap_limit: int = 20

    def __post_init__(self):
        self.lock = threading.RLock()
        self.mnemonic = Mnemonic("english")
        self.running = False
        self.synchronized = False
        self.loop = asyncio.get_event_loop()

    def start(self):
        self.running = True
        self.loop.create_task(periodic_task(self, self.process_pending, self.BLOCK_TIME))
        self.loop.create_task(periodic_task(self, self.maintain_addresses, self.ADDRESS_CHECK_TIME))

    def get_bip32_node(self):
        # TODO: replace pycoin with eth-account
        if self.mnemonic.check(self.key):
            return bitcoin_network.parse(f"P:{self.key}")
        return bitcoin_network.parse(self.key)

    def derive_address(self, n):
        bip32_node = self.get_bip32_node()
        public_key_bytes = bip32_node.subkey_for_path(f"0/{n}").sec(is_compressed=True)
        return PublicKey.from_compressed_bytes(public_key_bytes).to_checksum_address()

    async def process_pending(self):
        if not self.pending_invoices:
            return
        for address in self.pending_invoices:
            print(self.web3.eth.get_balance(address))

    def is_synchronized(self):
        with self.lock:
            return self.synchronized

    def is_used(self, address):
        return self.web3.eth.get_transaction_count(address) > 0 or self.web3.eth.get_balance(address) > 0

    def get_addresses(self, slice_start=None, slice_stop=None):
        return self.addresses[slice_start:slice_stop]

    def create_new_address(self):
        with self.lock:
            n = len(self.addresses)
            address = self.derive_address(n)
            self.addresses.append(address)
            return address

    def balance(self, idx):
        return self.web3.eth.get_balance(self.addresses[idx])

    async def maintain_addresses(self):
        limit = self.gap_limit
        with self.lock:
            while True:
                num_addr = len(self.addresses)
                if num_addr < limit:
                    self.synchronized = False
                    self.create_new_address()
                    continue
                last_few_addresses = self.get_addresses(slice_start=-limit)
                if any(map(self.is_used, last_few_addresses)):
                    self.synchronized = False
                    self.create_new_address()
                else:
                    break
            self.synchronized = True

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
        self.web3 = Web3(IPCProvider(self.ICPC_HOST))
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
        self.ICPC_HOST = self.config("ICPC_HOST", default=get_default_ipc_path())

    async def on_startup(self, app):
        await super().on_startup(app)

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

    def is_still_syncing(self, wallet=None):
        return not self.web3.isConnected() or self.web3.eth.syncing or (wallet and not wallet.is_synchronized())

    async def _get_wallet(self, id, req_method, xpub):
        wallet = error = None
        try:
            wallet = await self.load_wallet(xpub)
            if req_method in self.SKIP_NETWORK:
                return wallet, error
            while self.is_still_syncing(wallet):
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
    def add_peer(self, url, wallet=None):
        self.web3.geth.admin.add_peer(url)

    @rpc
    def broadcast(self, tx, wallet=None):
        return self.web3.eth.send_raw_transaction(tx)

    @rpc(requires_wallet=True)
    def clear_requests(self, wallet):
        self.wallets[wallet].invoices = {}
        self.wallets[wallet].pending_invoices = {}
        return True

    @rpc
    async def create(self, wallet=None):
        seed = self.make_seed()
        wallet = Wallet(seed, self.web3, self.BLOCK_TIME, self.ADDRESS_CHECK_TIME)
        await wallet.maintain_addresses()
        return {
            "seed": seed,
            "path": wallet.path,  # TODO: add
            "msg": WRITE_DOWN_SEED_MESSAGE,
        }

    @rpc
    def get_tx_status(self, tx, wallet=None):
        data = to_dict(self.web3.eth.get_transaction_receipt(tx))
        data["confirmations"] = max(0, self.web3.eth.block_number - data["blockNumber"])
        return data

    @rpc
    def getaddressbalance(self, address, wallet=None):
        return self.web3.eth.get_balance(address)

    @rpc
    def getaddresshistory(self, *args, **kwargs):
        raise NotImplementedError(NO_HISTORY_MESSAGE)

    @rpc(requires_wallet=True)
    def getbalance(self, wallet):
        return sum(self.web3.eth.get_balance(address) for address in self.wallets[wallet].addresses)

    @rpc
    def getfeerate(self, wallet=None):
        return self.web3.eth.gas_price

    @rpc
    def getinfo(self, wallet=None):
        if not self.web3.isConnected():
            return {"connected": False, "path": "", "version": self.VERSION}
        numblocks = self.web3.eth.block_number
        return {
            "blockchain_height": numblocks,
            "connected": self.web3.isConnected(),
            "gas_price": self.web3.eth.gas_price,
            "path": "",  # TODO: add
            "server": self.ICPC_HOST,
            "server_height": numblocks,
            "spv_nodes": len(self.web3.geth.admin.peers()),
            "version": self.VERSION,
        }

    @rpc
    def getmerkle(self, *args, **kwargs):
        raise NotImplementedError("Geth doesn't support get_proof correctly for now")

    @rpc
    def getservers(self, wallet=None):
        return [self.ICPC_HOST]

    @rpc
    def help(self, wallet=None):
        return list(self.supported_methods.keys())

    @rpc(requires_wallet=True)
    def ismine(self, address, wallet):
        return address in self.wallets[wallet].addresses

    @rpc
    def list_peers(self, wallet=None):
        return to_dict(self.web3.geth.admin.peers())

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
