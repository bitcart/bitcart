import asyncio
import contextlib
import json
import os
import traceback
from collections import deque, namedtuple
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from aiohttp import ClientError as AsyncClientError
from aiolimiter import AsyncLimiter
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import PrivateKey, PublicKey
from genericprocessor import (
    NOOP_PATH,
    BlockchainFeatures,
    BlockProcessorDaemon,
    Transaction,
    WalletDB,
    daemon_ctx,
    from_wei,
    str_to_bool,
    to_wei,
)
from genericprocessor import KeyStore as BaseKeyStore
from genericprocessor import Wallet as BaseWallet
from hexbytes import HexBytes
from mnemonic import Mnemonic
from storage import JSONEncoder as StorageJSONEncoder
from storage import Storage, decimal_to_string
from utils import (
    AbstractRPCProvider,
    MultipleProviderRPC,
    exception_retry_middleware,
    load_json_dict,
    modify_payment_url,
    rpc,
    try_cast_num,
)
from web3 import AsyncWeb3
from web3._utils.rpc_abi import RPC as ETHRPC
from web3.contract import AsyncContract
from web3.datastructures import AttributeDict
from web3.exceptions import ABIFunctionNotFound, BlockNotFound, TransactionNotFound, Web3Exception
from web3.exceptions import ValidationError as Web3ValidationError
from web3.middleware import async_simple_cache_middleware
from web3.middleware.geth_poa import async_geth_poa_middleware
from web3.providers.rpc import get_default_http_endpoint
from web3.types import RPCEndpoint, RPCResponse

Account.enable_unaudited_hdwallet_features()

daemon_ctx: ContextVar["ETHDaemon"]

EIP1559_PARAMS = ("maxFeePerGas", "maxPriorityFeePerGas")
FEE_PARAMS = EIP1559_PARAMS + ("gasPrice", "gas")

TX_DEFAULT_GAS = 21000

RPC_SOURCE = "Infura"


class JSONEncoder(StorageJSONEncoder):
    def default(self, obj):
        if isinstance(obj, AttributeDict):
            return dict(obj.items())
        if isinstance(obj, HexBytes):
            return str(obj.hex())
        return super().default(obj)


class MultipleRPCEthereumProvider(AsyncWeb3.AsyncHTTPProvider):
    def __init__(self, rpc: MultipleProviderRPC, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rpc = rpc

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        return await self.rpc.send_request(method, params)


class EthereumRPCProvider(AbstractRPCProvider, AsyncWeb3.AsyncHTTPProvider):
    web3: AsyncWeb3 = None  # patched later when it's created
    cooked_func = None

    async def prepare_for_requests(self):
        self.cooked_func = await self.request_func(self.web3, self.web3.middleware_onion)

    async def send_single_request(self, *args, **kwargs):
        return await self.cooked_func(*args, **kwargs)

    async def send_ping_request(self):
        return await self.send_single_request(ETHRPC.web3_clientVersion, [])


class ETHFeatures(BlockchainFeatures):
    web3: AsyncWeb3
    MAX_TRACE_DEPTH = 8

    def __init__(self, web3):
        self.web3 = web3
        self.get_block_safe = exception_retry_middleware(self.get_block, (BlockNotFound,), daemon_ctx.get().VERBOSE)
        self.get_block_receipts_safe = exception_retry_middleware(
            self.get_block_receipts, (BlockNotFound,), daemon_ctx.get().VERBOSE
        )
        self.get_tx_receipt_safe = exception_retry_middleware(
            self.get_tx_receipt, (TransactionNotFound,), daemon_ctx.get().VERBOSE
        )

    async def get_block_number(self):
        return await self.web3.eth.block_number

    async def is_connected(self):
        return await self.web3.is_connected()

    async def get_gas_price(self):
        return await self.web3.eth.gas_price

    async def get_transaction(self, tx):
        return await self.web3.eth.get_transaction(tx)

    async def get_tx_receipt(self, tx):
        return await self.web3.eth.get_transaction_receipt(tx)

    async def get_balance(self, address):
        return from_wei(await self.web3.eth.get_balance(address))

    async def get_block(self, block, *args, **kwargs):
        return await self.web3.eth.get_block(block, *args, **kwargs)

    async def get_block_receipts(self, block):
        return await self.web3.manager.coro_request("eth_getBlockReceipts", [hex(block)])

    async def get_block_txes(self, block):
        txes = (await self.get_block_safe(block, full_transactions=True))["transactions"]
        try:
            block_receipts = await self.get_block_receipts_safe(block)
            block_receipts = {x["transactionHash"]: x for x in block_receipts}
        except Exception:
            return txes
        for tx in txes:
            with contextlib.suppress(Exception):
                tx["status"] = block_receipts[self.get_tx_hash(tx)]["status"]
        return txes

    async def chain_id(self):
        return await self.web3.eth.chain_id

    def is_address(self, address):
        return AsyncWeb3.is_address(address) or AsyncWeb3.is_checksum_address(address)

    def normalize_address(self, address):
        return AsyncWeb3.to_checksum_address(address)

    async def get_payment_uri(self, address, amount, divisibility, contract=None):
        chain_id = await self.chain_id()
        amount_wei = to_wei(amount, divisibility)
        if contract:
            base_url = f"ethereum:{contract.address}@{chain_id}/transfer?address={address}"
            if amount_wei:
                base_url += f"&uint256={amount_wei}"
            return base_url
        base_url = f"ethereum:{address}@{chain_id}"
        if amount_wei:
            base_url += f"?value={amount_wei}"
        return base_url

    async def debug_trace_block(self, block_number):
        return await self.web3.manager.coro_request(
            "debug_traceBlockByNumber",
            [hex(block_number), {"tracer": "callTracer", "timeout": "10s"}],
        )

    async def process_tx_data(self, data):
        if "to" not in data:
            return
        if "status" in data and data["status"] == "0x0":
            return
        if "input" in data and data["input"].hex() != "0x" and (contract := daemon_ctx.get().contracts.get(data["to"])):
            try:
                function, args = contract.decode_function_input(data["input"])
                to_key = daemon_ctx.get().transfer_args.to
                value_key = daemon_ctx.get().transfer_args.value
                if (
                    (function.fn_name != "transfer" and function.fn_name != "transferFrom")
                    or to_key not in args
                    or value_key not in args
                ):
                    return
                from_addr = data["from"] if function.fn_name == "transfer" else args[daemon_ctx.get().transfer_args.from_addr]
                return Transaction(
                    str(data["hash"].hex()),
                    from_addr,
                    args[to_key],
                    args[value_key],
                    contract.address,
                    contract.divisibility,
                )
            except Exception:
                return
        return Transaction(str(data["hash"].hex()), data["from"], data["to"], data["value"])

    def find_all_trace_tx_outputs(self, tx_hash, from_addr, debug_data, depth=0):
        if debug_data["input"] == "0x" and "to" in debug_data:
            return [(tx_hash, from_addr, self.normalize_address(debug_data["to"]), int(debug_data.get("value", "0x0"), 16))]
        if depth + 1 >= self.MAX_TRACE_DEPTH:
            return []
        result = []
        for call in debug_data.get("calls", []):
            result.extend(self.find_all_trace_tx_outputs(tx_hash, from_addr, call, depth + 1))
        return result

    def find_all_trace_outputs(self, debug_data):
        result = []
        for tx in debug_data:
            if tx["result"]["input"] != "0x" and tx["result"].get("to") is not None:
                try:
                    self.web3.eth.contract(
                        address=self.normalize_address(tx["result"]["to"]), abi=daemon_ctx.get().ABI
                    ).decode_function_input(tx["result"]["input"])
                except Exception:
                    result.extend(self.find_all_trace_tx_outputs(tx["txHash"], tx["result"]["from"], tx["result"]))
        return result

    def get_tx_hash(self, tx_data):
        return tx_data["hash"].hex()

    def to_dict(self, obj):
        return json.loads(JSONEncoder(precision=daemon_ctx.get().DIVISIBILITY).encode(obj))

    def get_wallet_key(self, xpub, contract=None, **extra_params):
        key = xpub
        if contract:
            key += f"_{contract}"
        return key

    async def get_confirmations(self, tx_hash, data=None) -> int:
        data = data or await self.get_tx_receipt_safe(tx_hash)
        height = await self.get_block_number()
        return max(0, height - (data["blockNumber"] or height + 1) + 1)

    def current_server(self):
        return self.web3.provider.rpc.current_rpc.endpoint_uri


with open("daemons/abi/erc20.json") as f:
    ERC20_ABI = json.loads(f.read())

with open("daemons/tokens/erc20.json") as f:
    ERC20_TOKENS = json.loads(f.read())


# NOTE: there are 2 types of retry middlewares installed
# This middleware handles network error and unexpected RPC failures
# For BlockNotFound and TransactionNotFound we create _safe variants where needed
async def async_http_retry_request_middleware(make_request, w3):
    return exception_retry_middleware(
        make_request,
        (AsyncClientError, TimeoutError, asyncio.TimeoutError, Web3Exception),
        daemon_ctx.get().VERBOSE,
    )


RPC_ORIGIN = "metamask"
RPC_DEST = "internal"


@dataclass
class KeyStore(BaseKeyStore):
    account: Account = None

    def load_contract(self):
        if not self.contract:
            return
        try:
            self.contract = daemon_ctx.get().coin.normalize_address(self.contract)
        except Exception as e:
            raise Exception("Error loading wallet: invalid address") from e

    def __post_init__(self):
        self.load_contract()
        super().__post_init__()

    def load_account_from_key(self):
        self.account = None
        try:
            self.account = Account.from_mnemonic(self.key)
            self.seed = self.key
        except Exception:
            try:
                self.account = Account.from_key(self.key)
            except Exception:
                try:
                    self.public_key = PublicKey.from_compressed_bytes(AsyncWeb3.to_bytes(hexstr=self.key))
                    self.address = self.public_key.to_checksum_address()
                except Exception:
                    if not daemon_ctx.get().coin.is_address(self.key):
                        raise Exception("Error loading wallet: invalid address") from None
                    self.address = daemon_ctx.get().coin.normalize_address(self.key)
        if self.account:
            self.address = self.account.address
            self.private_key = self.account.key.hex()
            self.public_key = PublicKey.from_private(PrivateKey(AsyncWeb3.to_bytes(hexstr=self.private_key)))
        if self.public_key:
            self.public_key = AsyncWeb3.to_hex(self.public_key.to_compressed_bytes())

    def add_privkey(self, privkey):
        try:
            account = Account.from_key(privkey)
        except Exception as e:
            raise Exception("Invalid key provided") from e
        if account.address != self.address:
            raise Exception("Invalid private key imported: address mismatch")
        self.private_key = privkey
        self.account = account

    @classmethod
    def load(cls, db):
        return cls(key=db.get("key", ""), contract=db.get("contract", None))

    def dump(self):
        return {"key": self.key, "contract": self.contract}


@dataclass
class Wallet(BaseWallet):
    contract: str = None
    _token_fetched = False

    @property
    def contract_addr(self):
        return self.contract.address if self.contract else None

    async def fetch_token_info(self):
        self.symbol = (await daemon_ctx.get().readcontract(self.contract, "symbol")).upper()
        self.divisibility = await daemon_ctx.get().readcontract(self.contract, "decimals")
        self._token_fetched = True

    async def _start_init_vars(self):
        await super()._start_init_vars()
        if self.contract and not self._token_fetched:
            await self.fetch_token_info()

    async def balance(self, address=None):
        address = address or self.address
        if self.contract:
            return from_wei(await daemon_ctx.get().readcontract(self.contract, "balanceOf", address), self.divisibility)
        return await self.coin.get_balance(address)


TransferParams = namedtuple("TransferParams", ["from_addr", "to", "value"])


class ETHDaemon(BlockProcessorDaemon):
    name = "ETH"
    BASE_SPEC_FILE = "daemons/spec/eth.json"
    DEFAULT_PORT = 5002

    DIVISIBILITY = 18
    BLOCK_TIME = 5

    ABI = ERC20_ABI
    TOKENS = ERC20_TOKENS

    # modern transactions with maxPriorityFeePerGas
    # Disabled for now due to unpredictable gasPrice
    EIP1559_SUPPORTED = False
    DEFAULT_MAX_SYNC_BLOCKS = 300  # (60/12)=5*60 (a block every 12 seconds, max normal expiry time 60 minutes)

    UNIT = "wei"

    KEYSTORE_CLASS = KeyStore
    WALLET_CLASS = Wallet

    CONTRACT_TYPE = AsyncContract

    ARCHIVE_SUPPORTED = True

    def __init__(self):
        self._should_archive_seed_server = False
        super().__init__()
        self.env_update_hooks = {"server": self.update_server, "archive_server": self.update_archive_server}
        self.contracts = {}
        self.contract_cache = {"decimals": {}, "symbol": {}}
        self.transfer_args = self.parse_transfer_abi_args()

    def parse_transfer_abi_args(self):
        for obj in self.ABI:
            if obj["name"] == "transferFrom" and obj["type"] == "function":
                return TransferParams(obj["inputs"][0]["name"], obj["inputs"][1]["name"], obj["inputs"][2]["name"])
        raise Exception("Transfer function not found in ABI")

    async def update_archive_server(self, start_new=True):
        self.ARCHIVE_SERVER = self.ARCHIVE_SERVER.split(",")
        if not start_new:
            return
        await self.shutdown_coin(archive_only=True)
        await self.create_coin(archive=True)

    async def on_startup(self, app):
        await self.maybe_update_seed_server(start_new=False)
        self.trace_available = False
        self.trace_queue = asyncio.Queue()
        await self.create_coin(archive=True)
        with contextlib.suppress(Exception):
            await self.archive_coin.debug_trace_block(1)
            self.trace_available = True
        await super().on_startup(app)
        if self.trace_available:
            self.archive_limiter = AsyncLimiter(1, 1 / self.ARCHIVE_RATE_LIMIT)
            asyncio.gather(*[self.run_trace_queue() for _ in range(self.ARCHIVE_CONCURRENCY)])

    def load_env(self):
        super().load_env()
        self.ARCHIVE_SERVER = self.env("ARCHIVE_SERVER", default=",".join(self.SERVER)).split(",")
        self._should_archive_seed_server = len(self.ARCHIVE_SERVER) == 1 and self.ARCHIVE_SERVER[0] == self.SEED_SERVER
        self.ARCHIVE_CONCURRENCY = self.env("ARCHIVE_CONCURRENCY", default=20, cast=int)
        self.ARCHIVE_RATE_LIMIT = self.env("ARCHIVE_RATE_LIMIT", default=5, cast=int)

    @rpc
    async def getinfo(self, wallet=None):
        result = await super().getinfo(wallet)
        result["trace_enabled"] = self.trace_available
        return result

    async def run_trace_queue(self):
        while self.running:
            block_number = await self.trace_queue.get()
            try:
                debug_data = None
                for _ in range(5):
                    async with self.archive_limiter:
                        with contextlib.suppress(Exception):
                            debug_data = await self.archive_coin.debug_trace_block(block_number)
                    if debug_data:
                        break
                    await asyncio.sleep(5)
                if not debug_data:
                    raise Exception(f"Error getting debug trace for {block_number}")
                txes = [
                    Transaction(
                        x[0],
                        x[1],
                        x[2],
                        x[3],
                    )
                    for x in self.coin.find_all_trace_outputs(debug_data)
                ]
                [asyncio.ensure_future(self.process_transaction(tx)) for tx in txes]
            except Exception:
                if self.VERBOSE:
                    print(f"Error processing debug trace for {block_number}:")
                    print(traceback.format_exc())

    async def create_coin(self, archive=False):
        server_providers = []
        server_list = self.ARCHIVE_SERVER if archive else self.SERVER
        for server in server_list:
            # optimize requests by using correct headers
            provider = EthereumRPCProvider(
                server,
                request_kwargs={
                    "timeout": 5 * 60,
                    "headers": {
                        f"{RPC_SOURCE}-Source": f"{RPC_ORIGIN}/{RPC_DEST}",
                        "Content-Type": "application/json",
                    },
                },
            )
            provider.middlewares = [async_http_retry_request_middleware]
            server_providers.append(provider)
        provider = MultipleProviderRPC(server_providers)
        await provider.start()
        web3 = AsyncWeb3(MultipleRPCEthereumProvider(provider))
        web3.provider.middlewares = []
        web3.middleware_onion.clear()
        for provider in web3.provider.rpc.providers:
            provider.web3 = web3
            await provider.prepare_for_requests()  # required to call retry middlewares individually
        web3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
        web3.middleware_onion.add(async_simple_cache_middleware)
        if archive:
            self.archive_coin = ETHFeatures(web3)
        else:
            self.coin = ETHFeatures(web3)

    async def shutdown_coin(self, final=False, archive_only=False):
        if not archive_only:
            if not hasattr(self, "coin"):
                return
            await self.coin.web3.provider.rpc.stop()
        if (archive_only or final) and hasattr(self, "archive_coin"):
            if not hasattr(self, "archive_coin"):
                return
            await self.archive_coin.web3.provider.rpc.stop()

    def get_default_server_url(self):
        return get_default_http_endpoint()

    async def add_contract(self, contract, wallet):
        if not contract:
            return
        contract = self.coin.normalize_address(contract)
        if contract in self.contracts:
            self.wallets[wallet].contract = self.contracts[contract]
            return
        self.contracts[contract] = await self.create_web3_contract(contract)
        self.wallets[wallet].contract = self.contracts[contract]
        await self.wallets[wallet].fetch_token_info()

    async def create_web3_contract(self, contract):
        try:
            contract_obj = self.coin.web3.eth.contract(address=contract, abi=self.ABI)
            contract_obj.divisibility = await self.readcontract(contract_obj, "decimals")
            return contract_obj
        except Exception as e:
            raise Exception("Invalid contract address or non-ERC20 token") from e

    def _process_param(self, wallet, extra_params, key):
        if key in extra_params:
            value = extra_params[key]
            if getattr(wallet.keystore, key) != value:
                try:
                    cast_type = wallet.keystore.__dataclass_fields__[key].type
                    if value:
                        setattr(wallet.keystore, key, cast_type(value))
                    else:
                        setattr(wallet.keystore, key, cast_type())
                except Exception:
                    return
                wallet.db.put("keystore", wallet.keystore.dump())

    def process_extra_params(self, wallet, extra_params):
        pass

    async def load_wallet(self, xpub, contract, diskless=False, extra_params=None):
        if extra_params is None:
            extra_params = {}
        wallet_key = self.coin.get_wallet_key(xpub, contract, **extra_params)
        if wallet_key in self.wallets:
            await self.add_contract(contract, wallet_key)
            self.process_extra_params(self.wallets[wallet_key], extra_params)
            return self.wallets[wallet_key]
        if not xpub:
            return None

        if diskless:
            wallet = self.restore_wallet_from_text(xpub, contract, path=NOOP_PATH, **extra_params)
        else:
            wallet_dir = self.get_wallet_path()
            wallet_path = os.path.join(wallet_dir, wallet_key)
            if not os.path.exists(wallet_path):
                self.restore(xpub, wallet_path=wallet_path, contract=contract, **extra_params)
            storage = Storage(wallet_path)
            db = WalletDB(storage.read())
            wallet = self.WALLET_CLASS(self.coin, db, storage)
        self.process_extra_params(wallet, extra_params)
        self.wallets[wallet_key] = wallet
        self.wallets_updates[wallet_key] = deque(maxlen=self.POLLING_CAP)
        self.addresses[wallet.address].add(wallet_key)
        await self.add_contract(contract, wallet_key)
        await wallet.start(self.latest_blocks.copy())
        return wallet

    ### Methods ###
    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        await self.coin.web3.geth.admin.add_peer(url)

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        return self.coin.to_dict(await self.coin.web3.eth.send_raw_transaction(tx))

    @rpc(requires_network=True)
    async def getaddressbalance_contract(self, address, contract, wallet=None):
        divisibility = await self.readcontract(contract, "decimals")
        return {
            "balance": decimal_to_string(from_wei(await self.readcontract(contract, "balanceOf", address), divisibility)),
            "divisibility": divisibility,
        }

    @rpc(requires_network=True)
    async def get_default_gas(self, tx, wallet=None):
        tx_dict = load_json_dict(tx, "Invalid transaction").copy()
        tx_dict.pop("chainId", None)
        for param in FEE_PARAMS:
            tx_dict.pop(param, None)
        return await self.coin.web3.eth.estimate_gas(tx_dict)

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
            base_fee = (await self.coin.get_block_safe("latest")).baseFeePerGas
            fee = (from_wei(tx_dict["maxPriorityFeePerGas"]) + from_wei(base_fee)) * tx_dict["gas"]
        else:
            fee = from_wei(tx_dict["gasPrice"]) * tx_dict["gas"]
        return self.coin.to_dict(fee)

    @rpc
    def get_tokens(self, wallet=None):
        return self.TOKENS

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        return self.coin.to_dict(AsyncWeb3.keccak(hexstr=tx_data))

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        return len(AsyncWeb3.to_bytes(hexstr=tx_data))

    @rpc(requires_network=True)
    async def get_used_fee(self, tx_hash, wallet=None):
        tx_stats = await self.get_tx_status(tx_hash)
        return self.coin.to_dict(tx_stats["gasUsed"] * from_wei(tx_stats["effectiveGasPrice"]))

    @rpc
    def getabi(self, wallet=None):
        return self.ABI

    @rpc(requires_network=True)
    async def getnonce(self, address, pending=True, wallet=None):
        return await self.coin.web3.eth.get_transaction_count(
            address, block_identifier="pending" if str_to_bool(pending) else "latest"
        )

    @rpc(requires_network=True)
    async def gettransaction(self, tx, wallet=None):
        data = self.coin.to_dict(await self.coin.get_transaction(tx))
        data["confirmations"] = await self.coin.get_confirmations(tx, data)
        return data

    @rpc(requires_wallet=True)
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        unused, funded, balance = str_to_bool(unused), str_to_bool(funded), str_to_bool(balance)
        address = self.wallets[wallet].address
        addr_balance = await self.coin.get_balance(address)
        ntxs = await self.coin.web3.eth.get_transaction_count(address)
        if (unused and (addr_balance > 0 or ntxs > 0)) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, self.coin.to_dict(addr_balance))]
        return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", full_info=False, wallet=None):
        seed = Mnemonic(language).generate(nbits)
        if not full_info:
            return seed
        keystore = self.KEYSTORE_CLASS(key=seed)
        return {
            "seed": seed,
            "private_key": keystore.private_key,
            "address": keystore.address,
        }

    async def get_common_payto_params(self, address, nonce=None, gas_price=None, multiplier=None):
        nonce = nonce or await self.coin.web3.eth.get_transaction_count(address, block_identifier="pending")
        return {
            "nonce": nonce,
            "chainId": await self.coin.chain_id(),
            "from": address,
            **(await self.get_fee_params(gas_price=gas_price, multiplier=multiplier)),
        }

    @rpc(requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        address = kwargs["src_address"] if "src_address" in kwargs else self.wallets[wallet].address
        tx_dict = {
            "to": destination,
            "value": AsyncWeb3.to_wei(amount, "ether"),
            **(
                await self.get_common_payto_params(
                    address,
                    nonce=kwargs.get("nonce"),
                    gas_price=kwargs.get("gas_price"),
                    multiplier=kwargs.get("speed_multiplier"),
                )
            ),
        }
        if self.EIP1559_SUPPORTED:
            tx_dict["type"] = "0x2"
        if fee:
            tx_dict["maxFeePerGas"] = AsyncWeb3.to_wei(fee, "ether")
        if feerate:
            tx_dict["maxPriorityFeePerGas"] = AsyncWeb3.to_wei(feerate, "gwei")
        tx_dict["gas"] = int(gas) if gas else await self.get_default_gas(tx_dict)
        if unsigned:
            return tx_dict
        private_key = kwargs["private_key"] if "private_key" in kwargs else self.wallets[wallet].keystore.private_key
        if private_key is None:
            raise Exception("This is a watching-only wallet")
        return self._sign_transaction(tx_dict, private_key)

    async def get_fee_params(self, gas_price=None, multiplier=None):
        if self.EIP1559_SUPPORTED:
            block = await self.coin.get_block_safe("latest")
            max_priority_fee = await self.coin.web3.eth.max_priority_fee
            max_fee = block.baseFeePerGas * 2 + max_priority_fee
            return {"maxFeePerGas": max_fee, "maxPriorityFeePerGas": max_priority_fee}
        return {"gasPrice": gas_price or await self.getfeerate(multiplier=multiplier)}

    async def load_contract_exec_function(self, address, function, *args, **kwargs):
        kwargs.pop("wallet", None)
        if isinstance(address, self.CONTRACT_TYPE):
            contract = address
        else:
            try:
                address = self.coin.normalize_address(address)
            except Exception as e:
                raise Exception("Invalid address") from e
            contract = await self.create_web3_contract(address)
        # try converting args to int if possible
        args = [try_cast_num(x) for x in args]
        kwargs = {k: try_cast_num(v) for k, v in kwargs.items()}
        try:
            exec_function = getattr(contract.functions, function)
        except (ABIFunctionNotFound, AttributeError) as e:
            raise Exception(f"Contract ABI is missing {function} function") from e
        try:
            exec_function = exec_function(*args, **kwargs)
        except Web3ValidationError as e:
            raise Exception(f"Invalid arguments for {function} function") from e
        return exec_function

    @rpc(requires_network=True)
    async def readcontract(self, address, function, *args, **kwargs):
        cacheable_function = function in ("decimals", "symbol")
        if cacheable_function and (value := self.contract_cache[function].get(address)) is not None:
            return value
        exec_function = await self.load_contract_exec_function(address, function, *args, **kwargs)
        result = await exec_function.call()
        if cacheable_function:
            self.contract_cache[function][address] = result
        return result

    @rpc(requires_wallet=True)
    def signmessage(self, address=None, message=None, wallet=None):
        # Mimic electrum API
        if not address and not message:
            raise ValueError("No message specified")
        if not message:
            message = address
        return self.coin.to_dict(
            Account.sign_message(encode_defunct(text=message), private_key=self.wallets[wallet].key).signature
        )

    def _sign_transaction(self, tx, private_key):
        if private_key is None:
            raise Exception("This is a watching-only wallet")
        tx_dict = load_json_dict(tx, "Invalid transaction")
        return self.coin.to_dict(Account.sign_transaction(tx_dict, private_key=private_key).rawTransaction)

    @rpc(requires_wallet=True, requires_network=True)
    async def transfer(
        self,
        address,
        to,
        value,
        gas=None,
        unsigned=False,
        nonce=None,
        gas_price=None,
        speed_multiplier=None,
        fee=None,
        wallet=None,
    ):
        try:
            divisibility = await self.readcontract(address, "decimals")
            value = to_wei(Decimal(value), divisibility)
        except Exception as e:
            raise Exception("Invalid arguments for transfer function") from e
        return await self.writecontract(
            address,
            "transfer",
            to,
            value,
            gas=gas,
            unsigned=unsigned,
            nonce=nonce,
            gas_price=gas_price,
            speed_multiplier=speed_multiplier,
            fee=fee,
            wallet=wallet,
        )

    @rpc
    async def validatecontract(self, address, wallet=None):
        try:
            await self.create_web3_contract(self.coin.normalize_address(address))
            return True
        except Exception:
            return False

    @rpc
    def verifymessage(self, address, signature, message, wallet=None):
        return self.coin.normalize_address(
            Account.recover_message(encode_defunct(text=message), signature=signature)
        ) == self.coin.normalize_address(address)

    @rpc(requires_network=True)
    async def writecontract(self, address, function, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        unsigned = kwargs.pop("unsigned", False)
        gas = kwargs.pop("gas", None)
        nonce = kwargs.pop("nonce", None)
        gas_price = kwargs.pop("gas_price", None)
        multiplier = kwargs.pop("speed_multiplier", None)
        kwargs.pop("fee", None)  # TODO: better unify params
        wallet_address = kwargs.pop("src_address") if "src_address" in kwargs else self.wallets[wallet].address
        private_key = kwargs.pop("private_key") if "private_key" in kwargs else self.wallets[wallet].keystore.private_key
        exec_function = await self.load_contract_exec_function(address, function, *args, **kwargs)
        # pass gas here to avoid calling estimate_gas on an incomplete tx
        tx = await exec_function.build_transaction(
            {
                **await self.get_common_payto_params(
                    wallet_address,
                    nonce=nonce,
                    gas_price=gas_price,
                    multiplier=multiplier,
                ),
                "gas": TX_DEFAULT_GAS,
            }
        )
        tx["gas"] = int(gas) if gas else await self.get_default_gas(tx)
        if unsigned:
            return tx
        signed = self._sign_transaction(tx, private_key)
        return await self.broadcast(signed)

    @rpc
    async def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        if "/transfer" in url:
            return modify_payment_url("uint256", url, to_wei(amount, divisibility))
        return modify_payment_url("value", url, to_wei(amount, divisibility))


if __name__ == "__main__":
    daemon = ETHDaemon()
    daemon.start()
