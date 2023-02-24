import asyncio
import json
import weakref
from decimal import Decimal
from urllib.parse import urljoin

import httpx
import trontxsize
from aiohttp import ClientError as AsyncClientError
from aiohttp import ClientSession
from async_lru import alru_cache
from eth import ETHDaemon
from eth import KeyStore as ETHKeyStore
from eth import Transaction, daemon_ctx, from_wei, load_json_dict, str_to_bool, to_wei
from eth_account import Account
from genericprocessor import BlockchainFeatures
from mnemonic import Mnemonic
from tronpy import AsyncTron, async_tron, keys
from tronpy.abi import trx_abi
from tronpy.async_tron import AsyncContract, AsyncTransaction
from tronpy.exceptions import AddressNotFound
from utils import exception_retry_middleware, rpc

with open("daemons/tokens/trc20.json") as f:
    TRC20_TOKENS = json.loads(f.read())

mnemonic = Mnemonic("english")

TRX_ACCOUNT_PATH = "m/44'/195'/0'/0/0"

DEFAULT_FEE_LIMIT = 30_000_000  # 30 TRX


# For testing with aiohttp client (might be more stable)
class AsyncHTTPProvider:
    def __init__(
        self,
        endpoint_uri=None,
        timeout=10,
    ):
        self.endpoint_uri = endpoint_uri
        self.headers = {"User-Agent": "Tronpy/0.2"}
        self.client = None

    async def make_request(self, method, params=None):
        if self.client is None:
            self.client = ClientSession(headers=self.headers)
        if params is None:
            params = {}
        url = urljoin(self.endpoint_uri, method)
        async with self.client.post(url, json=params) as resp:
            resp.raise_for_status()
            return await resp.json()


async_tron.AsyncHTTPProvider = AsyncHTTPProvider  # monkey patch


class TRXFeatures(BlockchainFeatures):
    def __init__(self, web3):
        self.web3 = web3

    async def get_block_number(self):
        try:
            return await self.web3.get_latest_block_number()
        except Exception:
            block_data = await self.web3.get_latest_block()
            return block_data["block_header"]["raw_data"]["number"]

    async def is_connected(self):
        return True

    def find_chain_param(self, params, key, default=None):
        try:
            return next(filter(lambda x: x["key"] == key, params))["value"]
        except StopIteration:
            return default

    async def get_gas_price(self):
        params = await self.web3.get_chain_parameters()
        return self.find_chain_param(params, "getEnergyFee", 1)

    async def is_syncing(self):
        return False

    async def get_transaction(self, tx):
        return await self.web3.get_transaction(tx)

    async def get_tx_receipt(self, tx):
        return await self.web3.get_transaction_info(tx)

    async def get_balance(self, address):
        try:
            return await self.web3.get_account_balance(address)
        except AddressNotFound:
            return Decimal(0)

    async def get_block(self, block, *args, **kwargs):
        if block == "latest":
            block = None
        return (await self.web3.provider.make_request("wallet/getblockbynum", {"num": block, "detail": True})).get(
            "transactions", []
        )

    async def get_block_txes(self, block):
        return await self.get_block(block)

    async def chain_id(self):
        return 1

    def is_address(self, address):
        return keys.is_address(address)

    def normalize_address(self, address):
        return keys.to_base58check_address(address)

    async def get_peer_list(self):
        return await self.web3.list_nodes()

    async def get_payment_uri(self, req, divisibility, contract=None):
        return f"tron:{req.address}"

    async def process_tx_data(self, full_data):
        if len(full_data["raw_data"]["contract"]) == 0:
            return
        contract = full_data["raw_data"]["contract"][0]
        value = contract["parameter"]["value"]
        from_address = self.normalize_address(value["owner_address"])
        if contract["type"] == "TriggerSmartContract":
            contract_address = self.normalize_address(value["contract_address"])
            try:
                contract = await daemon_ctx.get().create_web3_contract(contract_address)
            except Exception:
                return
            divisibility = daemon_ctx.get().DECIMALS_CACHE[contract_address]
            data = bytes.fromhex(value["data"])
            function = contract.get_function_by_selector(data[:4])
            try:
                params = trx_abi.decode(["address", "uint256"], data[4:])
            except Exception:
                return
            if function.name != "transfer":
                return
            return Transaction(
                full_data["txID"], from_address, self.normalize_address(params[0]), params[1], contract_address, divisibility
            )

        if contract["type"] != "TransferContract":
            return
        return Transaction(full_data["txID"], from_address, self.normalize_address(value["to_address"]), value["amount"])

    def get_tx_hash(self, tx_data):
        return tx_data["txID"]

    def get_wallet_key(self, xpub, contract=None):
        key = xpub
        if contract:
            key += f"_{contract}"
        return key

    async def get_confirmations(self, tx_hash, data=None) -> int:
        data = data or await self.get_tx_receipt(tx_hash)
        height = await self.get_block_number()
        block_number = data.get("blockNumber", height + 1) or height + 1
        return max(0, height - block_number + 1)


class KeyStore(ETHKeyStore):
    def load_account_from_key(self):
        try:
            self.private_key = keys.PrivateKey.fromhex(
                Account.from_mnemonic(self.key, account_path=TRX_ACCOUNT_PATH).key.hex()[2:]
            )
            self.seed = self.key
        except Exception:
            try:
                self.private_key = keys.PrivateKey.fromhex(self.key)
            except Exception:
                try:
                    self.public_key = keys.PublicKey.fromhex(self.key)
                except Exception:
                    if not daemon_ctx.get().coin.is_address(self.key):
                        raise Exception("Error loading wallet: invalid address")
                    self.address = daemon_ctx.get().coin.normalize_address(self.key)
        if self.private_key is not None:
            self.public_key = self.private_key.public_key
            self.private_key = self.private_key.hex()
        if self.public_key is not None:
            self.address = self.public_key.to_base58check_address()
            self.public_key = self.public_key.hex()

    def add_privkey(self, privkey):
        try:
            private_key = keys.PrivateKey.fromhex(privkey)
        except Exception:
            raise Exception("Invalid key provided")
        address = private_key.public_key.to_base58check_address()
        if address != self.address:
            raise Exception("Invalid private key imported: address mismatch")
        self.private_key = privkey


TRON_ALIASES = ETHDaemon.ALIASES
TRON_ALIASES.update(
    {
        "get_default_energy": "get_default_gas",
    }
)


class TRXDaemon(ETHDaemon):
    name = "TRX"
    DEFAULT_PORT = 5009

    DIVISIBILITY = 6
    AMOUNTGEN_DIVISIBILITY = 6
    EIP1559_SUPPORTED = False
    DEFAULT_MAX_SYNC_BLOCKS = 300  # (60/3)=20*60 (a block every 3 seconds, keep up to 15 minutes of data)
    FIAT_NAME = "tron"

    CONTRACT_TYPE = AsyncContract

    KEYSTORE_CLASS = KeyStore

    TOKENS = TRC20_TOKENS

    ALIASES = TRON_ALIASES

    def __init__(self):
        super().__init__()
        self.CONTRACTS_CACHE = weakref.WeakValueDictionary()
        self.DECIMALS_CACHE = {}

    def create_coin(self):
        if self.SERVER and not self.SERVER.endswith("/"):
            self.SERVER += "/"
        provider = AsyncHTTPProvider(self.SERVER)
        provider.make_request = exception_retry_middleware(
            provider.make_request,
            (httpx.HTTPError, AsyncClientError, TimeoutError, asyncio.TimeoutError),
            self.VERBOSE,
        )
        self.coin = TRXFeatures(AsyncTron(provider, conf={"fee_limit": DEFAULT_FEE_LIMIT}))

    async def check_contract_logs(self, contract, divisibility, from_block=None, to_block=None):
        pass  # we do it right during block processing

    @alru_cache(maxsize=32)
    async def create_web3_contract(self, contract):
        try:
            value = self.CONTRACTS_CACHE.get(contract)
            if value is None:
                value = await self.coin.web3.get_contract(contract)
                self.DECIMALS_CACHE[contract] = await value.functions.decimals()
                self.CONTRACTS_CACHE[contract] = value

            return value
        except Exception as e:
            raise Exception("Invalid contract address or non-TRC20 token") from e

    async def start_contract_listening(self, contract):  # we don't start it here
        return await self.create_web3_contract(contract)

    def get_fx_contract(self, contract):
        return self.coin.normalize_address(contract)

    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        raise NotImplementedError("Tron APIs do not allow to add peers")

    @rpc(requires_network=True)
    async def gettransaction(self, tx, wallet=None):
        data = self.coin.to_dict(await self.coin.get_transaction(tx))
        data["confirmations"] = await self.coin.get_confirmations(tx)
        return data

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

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        tx_dict = load_json_dict(tx, "Invalid transaction")
        return (await self.coin.web3.broadcast(AsyncTransaction(tx_dict)))["txid"]

    @rpc(requires_network=True)
    async def getabi(self, address=None, wallet=None):
        if address is not None:
            return (await self.coin.web3.get_contract(address)).abi
        return self.ABI

    @rpc(requires_wallet=True, requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, unsigned=False, wallet=None, *args, **kwargs):
        address = self.wallets[wallet].address
        txn = self.coin.web3.trx.transfer(address, destination, to_wei(amount, self.DIVISIBILITY))
        if fee:
            txn = txn.fee_limit(to_wei(fee, self.DIVISIBILITY))
        tx_dict = await txn.build()
        if unsigned:
            return tx_dict.to_json()
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        return await self._sign_transaction(tx_dict.to_json(), self.wallets[wallet].keystore.private_key)

    async def _sign_transaction(self, tx, private_key):
        if private_key is None:
            raise Exception("This is a watching-only wallet")
        tx_dict = load_json_dict(tx, "Invalid transaction")
        return AsyncTransaction(tx_dict, self.coin.web3).sign(keys.PrivateKey.fromhex(private_key)).to_json()

    @rpc(requires_wallet=True)
    def signmessage(self, address=None, message=None, wallet=None):
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        # Mimic electrum API
        if not address and not message:
            raise ValueError("No message specified")
        if not message:
            message = address
        return keys.PrivateKey.fromhex(self.wallets[wallet].keystore.private_key).sign_msg(message.encode("utf-8")).hex()

    @rpc
    def verifymessage(self, address, signature, message, wallet=None):
        return keys.PublicKey.recover_from_msg(
            message.encode("utf-8"), keys.Signature.fromhex(signature)
        ).to_base58check_address() == self.coin.normalize_address(address)

    @rpc(requires_network=True)
    async def readcontract(self, address, function, *args, **kwargs):
        exec_function = await self.load_contract_exec_function(address, function, *args, **kwargs)
        return await exec_function

    @rpc(requires_wallet=True, requires_network=True)
    async def writecontract(self, address, function, *args, **kwargs):
        kwargs.pop("gas", None)
        wallet = kwargs.pop("wallet")
        unsigned = kwargs.pop("unsigned", False)
        fee = kwargs.pop("fee", None)
        exec_function = await self.load_contract_exec_function(address, function, *args, **kwargs)
        tx = (await exec_function).with_owner(self.wallets[wallet].address)
        if fee is not None:
            tx = tx.fee_limit(fee)
        tx = await tx.build()
        if unsigned:
            return tx.to_json()
        signed = await self._sign_transaction(tx.to_json(), self.wallets[wallet].keystore.private_key)
        return await self.broadcast(signed)

    @rpc(requires_network=True)
    async def get_used_fee(self, tx_hash, wallet=None):
        tx_stats = await self.get_tx_status(tx_hash)
        return self.coin.to_dict(from_wei(tx_stats.get("fee", 0)))

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        tx_dict = load_json_dict(tx_data, "Invalid transaction")
        return trontxsize.get_tx_size(tx_dict)

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        tx_dict = load_json_dict(tx_data, "Invalid transaction")
        return tx_dict["txID"]

    @rpc
    async def validatecontract(self, address, wallet=None):
        try:
            await self.create_web3_contract(self.coin.normalize_address(address))
            return True
        except Exception:
            return False

    @rpc(requires_network=True)
    async def get_default_gas(self, tx, wallet=None):  # actually energy in our case
        tx_dict = load_json_dict(tx, "Invalid transaction").copy()
        value = tx_dict["raw_data"]["contract"][0]["parameter"]["value"]
        if "contract_address" not in value:
            return 0
        contract = await self.create_web3_contract(value["contract_address"])
        data = bytes.fromhex(value["data"])
        function = contract.get_function_by_selector(data[:4])
        params = trx_abi.decode(["address", "uint256"], data[4:])
        response = await self.coin.web3.provider.make_request(
            "wallet/triggerconstantcontract",
            {
                "owner_address": keys.to_base58check_address(value["owner_address"]),
                "contract_address": keys.to_base58check_address(value["contract_address"]),
                "function_selector": function.function_signature,
                "parameter": function._prepare_parameter(*params),
                "visible": True,
            },
        )
        return response["energy_used"]

    @rpc(requires_network=True)
    async def get_default_fee(self, tx, wallet=None):
        tx_dict = load_json_dict(tx, "Invalid transaction")
        energy = await self.get_default_gas(tx_dict)
        bandwidth = self.get_tx_size(tx_dict)
        value = tx_dict["raw_data"]["contract"][0]["parameter"]["value"]
        to_address = value.get("to_address")
        is_account_create = False
        if to_address is not None:
            try:
                await self.coin.web3.get_account(to_address)
            except AddressNotFound:
                is_account_create = True
        address = value["owner_address"]
        resources = await self.coin.web3.get_account_resource(address)
        chain_params = await self.coin.web3.get_chain_parameters()
        bandwidth_cost = self.coin.find_chain_param(chain_params, "getTransactionFee", 1000)
        energy_cost = self.coin.find_chain_param(chain_params, "getEnergyFee", 1)
        user_available_net = resources.get("NetLimit", 0) - resources.get("NetUsed", 0)
        allowed_bandwidth = max(
            resources.get("freeNetLimit", 0) - resources.get("freeNetUsed", 0),
            user_available_net,
        )
        fee = Decimal(0)
        if is_account_create:
            if bandwidth > user_available_net:
                fee += from_wei(self.coin.find_chain_param(chain_params, "getCreateAccountFee", 100000), self.DIVISIBILITY)
            fee += from_wei(
                self.coin.find_chain_param(chain_params, "getCreateNewAccountFeeInSystemContract", 1000000), self.DIVISIBILITY
            )
        elif bandwidth > allowed_bandwidth:
            fee += bandwidth * from_wei(bandwidth_cost, self.DIVISIBILITY)
        if energy > 0:
            user_energy = resources.get("EnergyLimit", 0) - resources.get("EnergyUsed", 0)
            contract = await self.create_web3_contract(value["contract_address"])
            contract_creator = contract.origin_address
            creator_resources = await self.coin.web3.get_account_resource(contract_creator)
            creator_energy = creator_resources.get("EnergyLimit", 0) - creator_resources.get("EnergyUsed", 0)
            needed_energy = Decimal(energy) * (Decimal(contract.user_resource_percent) / Decimal(100))
            creator_needed_energy = min(
                creator_energy, Decimal(energy) * (Decimal(100 - contract.user_resource_percent) / Decimal(100))
            )
            needed_energy = energy - creator_needed_energy
            needed_energy -= min(user_energy, needed_energy)
            if needed_energy > 0:
                fee += needed_energy * from_wei(energy_cost, self.DIVISIBILITY)
        return self.coin.to_dict(fee)

    @rpc(requires_network=True)
    async def isactive(self, address, wallet=None):
        if not self.validateaddress(address):
            raise Exception("Invalid address")
        success_balance = True
        try:
            await self.coin.web3.get_account_balance(address)
        except Exception:
            success_balance = False
        return success_balance

    @rpc
    async def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        return url


if __name__ == "__main__":
    daemon = TRXDaemon()
    daemon.start()
