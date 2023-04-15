import asyncio
import json
import os
import traceback
from collections import deque
from decimal import Decimal

from aiohttp import ClientError as AsyncClientError
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keys.datatypes import PrivateKey, PublicKey
from genericprocessor import NOOP_PATH, BlockchainFeatures, BlockProcessorDaemon
from genericprocessor import KeyStore as BaseKeyStore
from genericprocessor import Transaction
from genericprocessor import Wallet as BaseWallet
from genericprocessor import WalletDB, daemon_ctx, from_wei, str_to_bool, to_wei
from hexbytes import HexBytes
from mnemonic import Mnemonic
from storage import JSONEncoder as StorageJSONEncoder
from storage import Storage
from utils import exception_retry_middleware, load_json_dict, modify_payment_url, rpc, try_cast_num
from web3 import Web3
from web3.contract import AsyncContract
from web3.datastructures import AttributeDict
from web3.exceptions import ABIFunctionNotFound, BlockNotFound, TransactionNotFound
from web3.exceptions import ValidationError as Web3ValidationError
from web3.exceptions import Web3Exception
from web3.middleware.geth_poa import async_geth_poa_middleware
from web3.providers.rpc import get_default_http_endpoint

Account.enable_unaudited_hdwallet_features()


EIP1559_PARAMS = ("maxFeePerGas", "maxPriorityFeePerGas")
FEE_PARAMS = EIP1559_PARAMS + ("gasPrice", "gas")

TX_DEFAULT_GAS = 21000


class JSONEncoder(StorageJSONEncoder):
    def default(self, obj):
        if isinstance(obj, AttributeDict):
            return {k: v for k, v in obj.items()}
        if isinstance(obj, HexBytes):
            return str(obj.hex())
        return super().default(obj)


class ETHFeatures(BlockchainFeatures):
    web3: Web3

    def __init__(self, web3):
        self.web3 = web3
        self.get_block_safe = exception_retry_middleware(self.get_block, (BlockNotFound,), daemon_ctx.get().VERBOSE)
        self.get_tx_receipt_safe = exception_retry_middleware(
            self.get_tx_receipt, (TransactionNotFound,), daemon_ctx.get().VERBOSE
        )

    async def get_block_number(self):
        return await self.web3.eth.block_number

    async def is_connected(self):
        return await self.web3.is_connected()

    async def get_gas_price(self):
        return await self.web3.eth.gas_price

    async def is_syncing(self):
        try:
            return await self.web3.eth.syncing
        except Exception:
            return False

    async def get_transaction(self, tx):
        return await self.web3.eth.get_transaction(tx)

    async def get_tx_receipt(self, tx):
        return await self.web3.eth.get_transaction_receipt(tx)

    async def get_balance(self, address):
        return from_wei(await self.web3.eth.get_balance(address))

    async def get_block(self, block, *args, **kwargs):
        return await self.web3.eth.get_block(block, *args, **kwargs)

    async def get_block_txes(self, block):
        return (await self.get_block_safe(block, full_transactions=True))["transactions"]

    async def chain_id(self):
        return await self.web3.eth.chain_id

    def is_address(self, address):
        return Web3.is_address(address) or Web3.is_checksum_address(address)

    def normalize_address(self, address):
        return Web3.to_checksum_address(address)

    async def get_peer_list(self):
        return await self.web3.geth.admin.peers()

    async def get_payment_uri(self, req, divisibility, contract=None):
        chain_id = await self.chain_id()
        amount_wei = to_wei(req.amount, divisibility)
        if contract:
            base_url = f"ethereum:{contract.address}@{chain_id}/transfer?address={req.address}"
            if amount_wei:
                base_url += f"&uint256={amount_wei}"
            return base_url
        base_url = f"ethereum:{req.address}@{chain_id}"
        if amount_wei:
            base_url += f"?value={amount_wei}"
        return base_url

    async def process_tx_data(self, data):
        return Transaction(str(data["hash"].hex()), data["from"], data["to"], data["value"])

    def get_tx_hash(self, tx_data):
        return tx_data["hash"].hex()

    def to_dict(self, obj):
        return json.loads(JSONEncoder(precision=daemon_ctx.get().DIVISIBILITY).encode(obj))

    def get_wallet_key(self, xpub, contract=None):
        key = xpub
        if contract:
            key += f"_{contract}"
        return key

    async def get_confirmations(self, tx_hash, data=None) -> int:
        data = data or await self.get_tx_receipt_safe(tx_hash)
        height = await self.get_block_number()
        return max(0, height - (data["blockNumber"] or height + 1) + 1)


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


class KeyStore(BaseKeyStore):
    account: Account = None
    contract: str = None

    def load_contract(self):
        if not self.contract:
            return
        try:
            self.contract = daemon_ctx.get().coin.normalize_address(self.contract)
        except Exception:
            raise Exception("Error loading wallet: invalid address")

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
                    self.public_key = PublicKey.from_compressed_bytes(Web3.to_bytes(hexstr=self.key))
                    self.address = self.public_key.to_checksum_address()
                except Exception:
                    if not daemon_ctx.get().coin.is_address(self.key):
                        raise Exception("Error loading wallet: invalid address")
                    self.address = daemon_ctx.get().coin.normalize_address(self.key)
        if self.account:
            self.address = self.account.address
            self.private_key = self.account.key.hex()
            self.public_key = PublicKey.from_private(PrivateKey(Web3.to_bytes(hexstr=self.private_key)))
        if self.public_key:
            self.public_key = Web3.to_hex(self.public_key.to_compressed_bytes())

    def add_privkey(self, privkey):
        try:
            account = Account.from_key(privkey)
        except Exception:
            raise Exception("Invalid key provided")
        if account.address != self.address:
            raise Exception("Invalid private key imported: address mismatch")
        self.private_key = privkey
        self.account = account

    @classmethod
    def load(cls, db):
        return cls(key=db.get("key", ""), contract=db.get("contract", None))

    def dump(self):
        return {"key": self.key, "contract": self.contract}


class Wallet(BaseWallet):
    contract: str = None
    _token_fetched = False

    async def fetch_token_info(self):
        self.symbol = (await daemon_ctx.get().readcontract(self.contract, "symbol")).upper()
        self.divisibility = await daemon_ctx.get().readcontract(self.contract, "decimals")
        self._token_fetched = True

    async def _start_init_vars(self):
        await super()._start_init_vars()
        if self.contract and not self._token_fetched:
            await self.fetch_token_info()

    async def _start_process_pending(self, blocks, current_height):
        await super()._start_process_pending(blocks, current_height)
        if self.contract:
            # process token transactions
            await daemon_ctx.get().check_contract_logs(
                self.contract,
                self.divisibility,
                from_block=self.latest_height + 1,
                to_block=min(self.latest_height + daemon_ctx.get().MAX_SYNC_BLOCKS, current_height),
            )

    async def balance(self):
        if self.contract:
            return from_wei(await daemon_ctx.get().readcontract(self.contract, "balanceOf", self.address), self.divisibility)
        return await self.coin.get_balance(self.address)


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

    def __init__(self):
        super().__init__()
        self.contracts = {}
        self.contract_heights = self.config.get_dict("contract_heights")
        self.contract_cache = {"decimals": {}, "symbol": {}}

    async def check_contract_logs(self, contract, divisibility, from_block=None, to_block=None):
        try:
            for tx_data in await contract.events.Transfer.get_logs(fromBlock=from_block, toBlock=to_block):
                try:
                    tx = Transaction(
                        str(tx_data["transactionHash"].hex()),
                        tx_data["args"]["from"],
                        tx_data["args"]["to"],
                        tx_data["args"]["value"],
                        contract.address,
                        divisibility,
                    )
                    await self.process_transaction(tx)
                except Exception:
                    if self.VERBOSE:
                        print(f"Error processing transaction {tx_data['transactionHash'].hex()}:")
                        print(traceback.format_exc())
        except Exception:
            if self.VERBOSE:
                print(f"Error getting logs on contract {contract.address}:")
                print(traceback.format_exc())

    def create_coin(self):
        self.coin = ETHFeatures(
            Web3(
                Web3.AsyncHTTPProvider(self.SERVER, request_kwargs={"timeout": 5 * 60}),
            )
        )
        self.coin.web3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
        self.coin.web3.middleware_onion.inject(async_http_retry_request_middleware, layer=0)

    def get_default_server_url(self):
        return get_default_http_endpoint()

    async def add_contract(self, contract, wallet):
        if not contract:
            return
        contract = self.coin.normalize_address(contract)
        if contract in self.contracts:
            self.wallets[wallet].contract = self.contracts[contract]
            return
        if contract not in self.contract_heights:
            self.contract_heights[contract] = await self.coin.get_block_number()
        self.contracts[contract] = await self.start_contract_listening(contract)
        self.wallets[wallet].contract = self.contracts[contract]
        await self.wallets[wallet].fetch_token_info()

    async def start_contract_listening(self, contract):
        contract_obj = await self.create_web3_contract(contract)
        divisibility = await self.readcontract(contract_obj, "decimals")
        self.loop.create_task(self.check_contracts(contract_obj, divisibility))
        return contract_obj

    async def create_web3_contract(self, contract):
        try:
            return self.coin.web3.eth.contract(address=contract, abi=self.ABI)
        except Exception as e:
            raise Exception("Invalid contract address or non-ERC20 token") from e

    async def check_contracts(self, contract, divisibility):
        while self.running:
            try:
                current_height = await self.coin.get_block_number()
                if current_height > self.contract_heights[contract.address]:
                    await self.check_contract_logs(
                        contract,
                        divisibility,
                        from_block=self.contract_heights[contract.address] + 1,
                        to_block=min(self.contract_heights[contract.address] + self.MAX_SYNC_BLOCKS, current_height),
                    )
                    self.contract_heights[contract.address] = current_height
            except Exception:
                if self.VERBOSE:
                    print("Error processing contract logs:")
                    print(traceback.format_exc())
            await asyncio.sleep(self.BLOCK_TIME)

    async def load_wallet(self, xpub, contract, diskless=False, extra_params={}):
        wallet_key = self.coin.get_wallet_key(xpub, contract)
        if wallet_key in self.wallets:
            await self.add_contract(contract, wallet_key)
            return self.wallets[wallet_key]
        if not xpub:
            return None

        if diskless:
            wallet = self.restore_wallet_from_text(xpub, contract, path=NOOP_PATH)
        else:
            wallet_dir = self.get_wallet_path()
            wallet_path = os.path.join(wallet_dir, wallet_key)
            if not os.path.exists(wallet_path):
                self.restore(xpub, wallet_path=wallet_path, contract=contract)
            storage = Storage(wallet_path)
            db = WalletDB(storage.read())
            wallet = Wallet(self.coin, db, storage)
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
        return self.coin.to_dict(Web3.keccak(hexstr=tx_data))

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        return len(Web3.to_bytes(hexstr=tx_data))

    @rpc(requires_network=True)
    async def get_used_fee(self, tx_hash, wallet=None):
        tx_stats = await self.get_tx_status(tx_hash)
        return self.coin.to_dict(tx_stats["gasUsed"] * from_wei(tx_stats["effectiveGasPrice"]))

    @rpc
    def getabi(self, wallet=None):
        return self.ABI

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
        else:
            return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", wallet=None):
        return Mnemonic(language).generate(nbits)

    async def get_common_payto_params(self, address):
        nonce = await self.coin.web3.eth.get_transaction_count(address, block_identifier="pending")
        return {
            "nonce": nonce,
            "chainId": await self.coin.chain_id(),
            "from": address,
            **(await self.get_fee_params()),
        }

    @rpc(requires_wallet=True, requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        address = self.wallets[wallet].address
        tx_dict = {
            "to": destination,
            "value": Web3.to_wei(amount, "ether"),
            **(await self.get_common_payto_params(address)),
        }
        if self.EIP1559_SUPPORTED:
            tx_dict["type"] = "0x2"
        if fee:
            tx_dict["maxFeePerGas"] = Web3.to_wei(fee, "ether")
        if feerate:
            tx_dict["maxPriorityFeePerGas"] = Web3.to_wei(feerate, "gwei")
        tx_dict["gas"] = int(gas) if gas else await self.get_default_gas(tx_dict)
        if unsigned:
            return tx_dict
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        return self._sign_transaction(tx_dict, self.wallets[wallet].keystore.private_key)

    async def get_fee_params(self):
        if self.EIP1559_SUPPORTED:
            block = await self.coin.get_block_safe("latest")
            max_priority_fee = await self.coin.web3.eth.max_priority_fee
            max_fee = block.baseFeePerGas * 2 + max_priority_fee
            return {"maxFeePerGas": max_fee, "maxPriorityFeePerGas": max_priority_fee}
        return {"gasPrice": await self.getfeerate()}

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
    async def transfer(self, address, to, value, gas=None, unsigned=False, wallet=None):
        try:
            divisibility = await self.readcontract(address, "decimals")
            value = to_wei(Decimal(value), divisibility)
        except Exception:
            raise Exception("Invalid arguments for transfer function")
        return await self.writecontract(address, "transfer", to, value, gas=gas, unsigned=unsigned, wallet=wallet)

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

    @rpc(requires_wallet=True, requires_network=True)
    async def writecontract(self, address, function, *args, **kwargs):
        wallet = kwargs.pop("wallet")
        unsigned = kwargs.pop("unsigned", False)
        gas = kwargs.pop("gas", None)
        exec_function = await self.load_contract_exec_function(address, function, *args, **kwargs)
        # pass gas here to avoid calling estimate_gas on an incomplete tx
        tx = await exec_function.build_transaction(
            {**await self.get_common_payto_params(self.wallets[wallet].address), "gas": TX_DEFAULT_GAS}
        )
        tx["gas"] = int(gas) if gas else await self.get_default_gas(tx)
        if unsigned:
            return tx
        signed = self._sign_transaction(tx, self.wallets[wallet].keystore.private_key)
        return await self.broadcast(signed)

    @rpc
    async def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        if "/transfer" in url:
            return modify_payment_url("uint256", url, to_wei(amount, divisibility))
        return modify_payment_url("value", url, to_wei(amount, divisibility))


if __name__ == "__main__":
    daemon = ETHDaemon()
    daemon.start()
