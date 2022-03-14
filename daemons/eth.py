import asyncio
import functools
import inspect
import json
import traceback
from dataclasses import InitVar, dataclass, field
from typing import ClassVar

from base import BaseDaemon
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import PrivateKey, PublicKey
from hexbytes import HexBytes
from mnemonic import Mnemonic
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
# TODO: limit sync post-reboot to (60/12)*60=5*60=300 blocks (max expiry time)

STR_TO_BOOL_MAPPING = {
    "true": True,
    "yes": True,
    "1": True,
    "false": False,
    "no": False,
    "0": False,
}  # common str -> bool conversions


def str_to_bool(s):
    if isinstance(s, bool):
        return s
    s = s.lower()

    if s in STR_TO_BOOL_MAPPING:
        return STR_TO_BOOL_MAPPING[s]
    return False


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
                    if not Web3.isAddress(self.key) and not Web3.isChecksumAddress(self.key):
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


@dataclass
class Wallet:
    key: InitVar[str]
    web3: Web3
    BLOCK_TIME: ClassVar[int]
    ADDRESS_CHECK_TIME: ClassVar[int]
    keystore: KeyStore = field(init=False)
    path: str = ""

    def __post_init__(self, key):
        self.keystore = KeyStore(key=key)
        self.running = False
        self.loop = asyncio.get_event_loop()

    def start(self):
        self.running = True

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


class ETHDaemon(BaseDaemon):
    name = "ETH"
    BASE_SPEC_FILE = "daemons/spec/eth.json"
    DEFAULT_PORT = 5002
    ALIASES = {
        "clear_invoices": "clear_requests",
        "commands": "help",
        "get_transaction": "gettransaction",
        "getunusedaddress": "getaddress",
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

    async def process_block(self, start_height, end_height):
        for block_number in range(start_height, end_height + 1):
            for tx in (await self.web3.eth.get_block(block_number, full_transactions=True))["transactions"]:
                pass

    async def process_pending(self):
        while self.running:
            try:
                current_height = await self.web3.eth.block_number
                tasks = []
                for block_number in range(self.latest_height + 1, current_height + 1, CHUNK_SIZE):
                    tasks.append(self.process_block(block_number, min(block_number + CHUNK_SIZE - 1, current_height)))
                await asyncio.gather(*tasks, return_exceptions=True)
                self.latest_height = current_height
            except Exception:
                if self.VERBOSE:
                    print("Error processing pending blocks:")
                    print(traceback.format_exc())
            await asyncio.sleep(self.BLOCK_TIME)

    async def on_shutdown(self, app):
        self.running = False
        for wallet in self.wallets.values():
            wallet.stop()
        await super().on_shutdown(app)

    def get_method_data(self, method):
        return self.supported_methods[method]

    def get_exception_message(self, e):
        return get_exception_message(e)

    async def load_wallet(self, xpub):
        if xpub in self.wallets:
            return self.wallets[xpub]
        if not xpub:
            return None

        wallet = Wallet(xpub, self.web3)
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

    @rpc
    async def broadcast(self, tx, wallet=None):
        return to_dict(await self.web3.eth.send_raw_transaction(tx))

    @rpc(requires_wallet=True)
    def clear_requests(self, wallet):
        return True

    @rpc(requires_wallet=True)
    def close_wallet(self, wallet):
        self.wallets[wallet].stop()
        del self.wallets[wallet]
        return True

    @rpc
    async def create(self, wallet=None):
        seed = self.make_seed()
        wallet = Wallet(seed, self.web3)
        return {
            "seed": seed,
            "path": wallet.path,  # TODO: add
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
    def getseed(self, *args, wallet=None):
        if not self.wallets[wallet].keystore.has_seed():
            raise Exception("This wallet has no seed words")
        return self.wallets[wallet].keystore.seed

    @rpc(requires_wallet=True)
    def getpubkeys(self, *args, wallet=None):
        return self.wallets[wallet].keystore.public_key

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

    @rpc
    def list_wallets(self, wallet=None):
        return [
            {"path": "", "synchronized": wallet_obj.is_synchronized()} for wallet_obj in self.wallets.values()
        ]  # TODO: add path

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
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None):
        address = self.wallets[wallet].address
        nonce = await self.web3.eth.get_transaction_count(address)
        tx_dict = {
            "type": "0x2",
            "from": self.wallets[wallet].address,
            "to": destination,
            "nonce": nonce,
            "value": Web3.toWei(amount, "ether"),
            "chainId": await self.web3.eth.chain_id,
            "gas": int(gas) or 21000,
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
    def restore(self, text, wallet=None):
        try:
            Wallet(text, self.web3)
        except Exception as e:
            raise Exception("Invalid key provided") from e
        return {
            "path": "",  # TODO: add
            "msg": "",
        }

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
        return Web3.isAddress(address) or Web3.isChecksumAddress(address)

    @rpc
    def verifymessage(self, address, signature, message, wallet=None):
        return Web3.toChecksumAddress(
            Account.recover_message(encode_defunct(text=message), signature=signature)
        ) == Web3.toChecksumAddress(address)

    @rpc
    def version(self, wallet=None):
        return self.VERSION


if __name__ == "__main__":
    daemon = ETHDaemon()
    daemon.start()
