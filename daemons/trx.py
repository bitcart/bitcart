import json
from decimal import Decimal

import eth
import trontxsize
from eth_account import Account
from mnemonic import Mnemonic
from tronpy import AsyncTron, keys
from tronpy.abi import trx_abi
from tronpy.async_tron import AsyncContract, AsyncHTTPProvider, AsyncTransaction
from tronpy.exceptions import AddressNotFound
from utils import rpc

with open("daemons/tokens/trc20.json") as f:
    TRC20_TOKENS = json.loads(f.read())

mnemonic = Mnemonic("english")

TRX_ACCOUNT_PATH = "m/44'/195'/0'/0/0"


async def get_block_number(self):
    try:
        return await self.web3.get_latest_block_number()
    except Exception:
        block_data = await self.web3.get_latest_block()
        return block_data["block_header"]["raw_data"]["number"]


async def is_connected(self):
    return True


def find_chain_param(params, key, default=None):
    try:
        return next(filter(lambda x: x["key"] == key, params))["value"]
    except StopIteration:
        return default


async def get_gas_price(self):
    params = await self.web3.get_chain_parameters()
    return find_chain_param(params, "getEnergyFee", 1)


async def eth_syncing(self):
    return False


def get_transaction(self, tx):
    return self.web3.get_transaction(tx)


def get_tx_receipt(self, tx):
    return self.web3.get_transaction_info(tx)


async def eth_get_balance(web3, address):
    try:
        return eth.to_wei(await web3.get_account_balance(address), 6)
    except AddressNotFound:
        return 0


async def eth_get_block(self, block, *args, **kwargs):
    if block == "latest":
        block = None
    return (await self.web3.provider.make_request("wallet/getblockbynum", {"num": block, "detail": True})).get(
        "transactions", []
    )


async def eth_get_block_txes(self, block):
    return await eth_get_block(self, block)


CONTRACTS_CACHE = {}
DECIMALS_CACHE = {}


async def eth_process_tx_data(self, full_data):
    if len(full_data["raw_data"]["contract"]) == 0:
        return
    contract = full_data["raw_data"]["contract"][0]
    value = contract["parameter"]["value"]
    if contract["type"] == "TriggerSmartContract":
        contract_address = normalize_address(value["contract_address"])
        try:
            contract = await self.create_web3_contract(contract_address)
        except Exception:
            return
        divisibility = self.DECIMALS_CACHE[contract_address]
        data = bytes.fromhex(value["data"])
        function = contract.get_function_by_selector(data[:4])
        try:
            params = trx_abi.decode(["address", "uint256"], data[4:])
        except Exception:
            return
        if function.name != "transfer":
            return
        return eth.Transaction(full_data["txID"], normalize_address(params[0]), params[1], contract_address, divisibility)

    if contract["type"] != "TransferContract":
        return
    return eth.Transaction(full_data["txID"], normalize_address(value["to_address"]), value["amount"])


async def eth_chain_id(self):
    return 1


def is_address(address):
    return keys.is_address(address)


def normalize_address(address):
    return keys.to_base58check_address(address)


def get_peer_list(self):
    return self.web3.list_nodes()


async def get_payment_uri(self, req):
    return f"tron:{req.address}"


async def check_contract_logs(contract, divisibility, from_block=None, to_block=None):
    pass  # we do it right during block processing


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
                if not is_address(self.key):
                    raise Exception("Error loading wallet: invalid address")
                self.address = normalize_address(self.key)
    if self.private_key is not None:
        self.public_key = self.private_key.public_key
        self.private_key = self.private_key.hex()
    if self.public_key is not None:
        self.address = self.public_key.to_base58check_address()
        self.public_key = self.public_key.hex()


def keystore_add_privkey(self, privkey):
    try:
        private_key = keys.PrivateKey.fromhex(privkey)
    except Exception:
        raise Exception("Invalid key provided")
    address = private_key.public_key.to_base58check_address()
    if address != self.address:
        raise Exception("Invalid private key imported: address mismatch")
    self.private_key = privkey


def get_tx_hash(tx_data):
    return tx_data["txID"]


TRON_ALIASES = eth.ETHDaemon.ALIASES
TRON_ALIASES.update(
    {
        "get_default_energy": "get_default_gas",
    }
)


class TRXDaemon(eth.ETHDaemon):
    name = "TRX"
    DEFAULT_PORT = 5009

    DIVISIBILITY = 6
    AMOUNTGEN_DIVISIBILITY = 6
    EIP1559_SUPPORTED = False
    DEFAULT_MAX_SYNC_BLOCKS = 1200  # (60/3)=20*60 (a block every 3 seconds, max normal expiry time 60 minutes)
    FIAT_NAME = "tron"

    CONTRACT_TYPE = AsyncContract

    TOKENS = TRC20_TOKENS

    ALIASES = TRON_ALIASES

    def __init__(self):
        super().__init__()
        self.CONTRACTS_CACHE = {}
        self.DECIMALS_CACHE = {}

    def create_web3(self):
        if self.SERVER and not self.SERVER.endswith("/"):
            self.SERVER += "/"
        self.web3 = AsyncTron(AsyncHTTPProvider(self.SERVER))

    async def on_shutdown(self, app):
        await super().on_shutdown(app)

    async def create_web3_contract(self, contract):
        try:
            value = self.CONTRACTS_CACHE.get(contract)
            if value is None:
                value = await self.web3.get_contract(contract)
                self.DECIMALS_CACHE[contract] = await value.functions.decimals()
                self.CONTRACTS_CACHE[contract] = value

            return value
        except Exception as e:
            raise Exception("Invalid contract address or non-TRC20 token") from e

    async def start_contract_listening(self, contract):  # we don't start it here
        return await self.create_web3_contract(contract)

    def get_fx_contract(self, contract):
        return normalize_address(contract)

    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        raise NotImplementedError("Tron APIs do not allow to add peers")

    @rpc(requires_network=True)
    async def gettransaction(self, tx, wallet=None):
        data = eth.to_dict(await get_transaction(self, tx))
        data["confirmations"] = max(0, await get_block_number(self) - (await get_tx_receipt(self, tx))["blockNumber"] + 1)
        return data

    @rpc(requires_wallet=True)
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        unused, funded, balance = eth.str_to_bool(unused), eth.str_to_bool(funded), eth.str_to_bool(balance)
        address = self.wallets[wallet].address
        addr_balance = await eth.get_balance(self.web3, address)
        if (unused and (addr_balance > 0)) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, eth.to_dict(addr_balance))]
        else:
            return [address]

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        tx_dict = eth.load_json_dict(tx, "Invalid transaction")
        return (await self.web3.broadcast(AsyncTransaction(tx_dict)))["txid"]

    @rpc(requires_network=True)
    async def getabi(self, address=None, wallet=None):
        if address is not None:
            return (await self.web3.get_contract(address)).abi
        return self.ABI

    @rpc(requires_wallet=True, requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, unsigned=False, wallet=None, *args, **kwargs):
        address = self.wallets[wallet].address
        txn = self.web3.trx.transfer(address, destination, eth.to_wei(amount, self.DIVISIBILITY))
        if fee:
            txn = txn.fee_limit(eth.to_wei(fee, self.DIVISIBILITY))
        tx_dict = await txn.build()
        if unsigned:
            return tx_dict.to_json()
        if self.wallets[wallet].is_watching_only():
            raise Exception("This is a watching-only wallet")
        return await self._sign_transaction(tx_dict.to_json(), self.wallets[wallet].keystore.private_key)

    async def _sign_transaction(self, tx, private_key):
        if private_key is None:
            raise Exception("This is a watching-only wallet")
        tx_dict = eth.load_json_dict(tx, "Invalid transaction")
        return AsyncTransaction(tx_dict, self.web3).sign(keys.PrivateKey.fromhex(private_key)).to_json()

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
        ).to_base58check_address() == normalize_address(address)

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
        return eth.to_dict(eth.from_wei(tx_stats.get("fee", 0)))

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        tx_dict = eth.load_json_dict(tx_data, "Invalid transaction")
        return trontxsize.get_tx_size(tx_dict)

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        tx_dict = eth.load_json_dict(tx_data, "Invalid transaction")
        return tx_dict["txID"]

    @rpc
    async def validatecontract(self, address, wallet=None):
        try:
            await self.create_web3_contract(normalize_address(address))
            return True
        except Exception:
            return False

    @rpc(requires_network=True)
    async def get_default_gas(self, tx, wallet=None):  # actually energy in our case
        tx_dict = eth.load_json_dict(tx, "Invalid transaction").copy()
        value = tx_dict["raw_data"]["contract"][0]["parameter"]["value"]
        if "contract_address" not in value:
            return 0
        contract = await self.create_web3_contract(value["contract_address"])
        data = bytes.fromhex(value["data"])
        function = contract.get_function_by_selector(data[:4])
        params = trx_abi.decode(["address", "uint256"], data[4:])
        response = await self.web3.provider.make_request(
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
        tx_dict = eth.load_json_dict(tx, "Invalid transaction")
        energy = await self.get_default_gas(tx_dict)
        bandwidth = self.get_tx_size(tx_dict)
        value = tx_dict["raw_data"]["contract"][0]["parameter"]["value"]
        address = value["owner_address"]
        resources = await self.web3.get_account_resource(address)
        chain_params = await self.web3.get_chain_parameters()
        bandwidth_cost = find_chain_param(chain_params, "getTransactionFee", 1000)
        energy_cost = find_chain_param(chain_params, "getEnergyFee", 1)
        allowed_bandwidth = max(
            resources.get("freeNetLimit", 0) - resources.get("freeNetUsed", 0),
            resources.get("NetLimit", 0) - resources.get("NetUsed", 0),
        )
        fee = Decimal(0)
        if allowed_bandwidth < bandwidth:
            fee += bandwidth * eth.from_wei(bandwidth_cost, self.DIVISIBILITY)
        if energy > 0:
            user_energy = resources.get("EnergyLimit", 0) - resources.get("EnergyUsed", 0)
            contract = await self.create_web3_contract(value["contract_address"])
            contract_creator = contract.origin_address
            creator_resources = await self.web3.get_account_resource(contract_creator)
            creator_energy = creator_resources.get("EnergyLimit", 0) - creator_resources.get("EnergyUsed", 0)
            needed_energy = Decimal(energy) * (Decimal(contract.user_resource_percent) / Decimal(100))
            creator_needed_energy = min(
                creator_energy, Decimal(energy) * (Decimal(100 - contract.user_resource_percent) / Decimal(100))
            )
            needed_energy = energy - creator_needed_energy
            needed_energy -= min(user_energy, needed_energy)
            if needed_energy > 0:
                fee += needed_energy * eth.from_wei(energy_cost, self.DIVISIBILITY)
        return eth.to_dict(fee)

    @rpc(requires_network=True)
    async def isactive(self, address, wallet=None):
        if not self.validateaddress(address):
            raise Exception("Invalid address")
        success_balance = True
        try:
            await self.web3.get_account_balance(address)
        except Exception:
            success_balance = False
        return success_balance


if __name__ == "__main__":
    eth.get_block_number = get_block_number
    eth.is_connected = is_connected
    eth.get_gas_price = get_gas_price
    eth.eth_syncing = eth_syncing
    eth.get_transaction = get_transaction
    eth.get_tx_receipt = get_tx_receipt
    eth.eth_get_balance = eth_get_balance
    eth.eth_get_block = eth_get_block
    eth.load_account_from_key = load_account_from_key
    eth.eth_get_block_txes = eth_get_block_txes
    eth.eth_chain_id = eth_chain_id
    eth.is_address = is_address
    eth.normalize_address = normalize_address
    eth.get_peer_list = get_peer_list
    eth.get_payment_uri = get_payment_uri
    eth.keystore_add_privkey = keystore_add_privkey
    eth.check_contract_logs = check_contract_logs
    eth.eth_process_tx_data = eth_process_tx_data
    eth.get_tx_hash = get_tx_hash
    eth.daemon = TRXDaemon()
    eth.daemon.start()
