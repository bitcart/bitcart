import json
import os
import re
from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from aiohttp import ClientSession
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
from storage import Storage, decimal_to_string
from utils import AbstractRPCProvider, MultipleProviderRPC, load_json_dict, modify_payment_url, rpc

SUI_COIN_TYPE = "0x2::sui::SUI"
SUI_DIVISIBILITY = 9
SUI_ADDRESS_RE = re.compile(r"^0x[0-9a-f]{64}$")
SUI_TRANSACTION_OPTIONS = {
    "showInput": True,
    "showEffects": True,
    "showBalanceChanges": True,
}
SUI_MULTI_GET_CHUNK_SIZE = 50
SUI_RPC_TIMEOUT = 300
SUI_SERVERS = {
    "mainnet": "https://fullnode.mainnet.sui.io:443",
    "testnet": "https://fullnode.testnet.sui.io:443",
    "devnet": "https://fullnode.devnet.sui.io:443",
}
SUI_SUCCESS_STATUS = "success"


def is_successful_transaction(data):
    return data.get("effects", {}).get("status", {}).get("status") == SUI_SUCCESS_STATUS


def get_address_owner(change):
    owner = change.get("owner", {})
    if not isinstance(owner, dict):
        return None
    return owner.get("AddressOwner")


def iter_chunks(items, chunk_size):
    for index in range(0, len(items), chunk_size):
        yield items[index : index + chunk_size]


def parse_gas_used(gas_used):
    computation = int(gas_used.get("computationCost", 0))
    storage = int(gas_used.get("storageCost", 0))
    rebate = int(gas_used.get("storageRebate", 0))
    return max(0, computation + storage - rebate)


def normalize_sui_address(address):
    address = address.lower()
    if not address.startswith("0x"):
        raise ValueError("Invalid SUI address")
    body = address[2:]
    if len(body) > 64 or not body or not all(char in "0123456789abcdef" for char in body):
        raise ValueError("Invalid SUI address")
    return f"0x{body.rjust(64, '0')}"


class SUIRPCProvider(AbstractRPCProvider):
    def __init__(self, endpoint_uri):
        self.endpoint_uri = endpoint_uri
        self.session: ClientSession | None = None
        self.request_id = 0

    def _build_payload(self, method, params):
        self.request_id += 1
        return {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or []}

    def _get_session(self):
        if self.session is None:
            self.session = ClientSession()
        return self.session

    async def send_single_request(self, method, params=None):
        session = self._get_session()
        async with session.post(
            self.endpoint_uri,
            json=self._build_payload(method, params),
            timeout=SUI_RPC_TIMEOUT,
        ) as response:
            response.raise_for_status()
            result = await response.json()
        if "error" in result:
            raise Exception(result["error"])
        return result["result"]

    async def send_ping_request(self):
        return await self.send_single_request("sui_getLatestCheckpointSequenceNumber")

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None


class SUIRPC(MultipleProviderRPC):
    async def stop(self):
        await super().stop()
        for provider in self.providers:
            await provider.close()


class SUIFeatures(BlockchainFeatures):
    def __init__(self, rpc):
        self.rpc = rpc

    async def _request(self, method, params=None):
        return await self.rpc.send_request(method, params or [])

    async def get_block_number(self):
        return int(await self._request("sui_getLatestCheckpointSequenceNumber"))

    async def is_connected(self):
        try:
            await self.get_block_number()
            return True
        except Exception:
            return False

    async def get_transaction(self, tx):
        return await self._request("sui_getTransactionBlock", [tx, SUI_TRANSACTION_OPTIONS])

    async def get_tx_receipt(self, tx):
        return await self.get_transaction(tx)

    async def get_confirmations(self, tx_hash, data=None):
        data = data or await self.get_tx_receipt(tx_hash)
        checkpoint = data.get("checkpoint")
        if checkpoint is None:
            return 0
        height = await self.get_block_number()
        return max(0, height - int(checkpoint) + 1)

    async def get_balance(self, address):
        result = await self._request("suix_getBalance", [self.normalize_address(address), SUI_COIN_TYPE])
        return from_wei(int(result["totalBalance"]), SUI_DIVISIBILITY)

    async def get_block(self, block, *args, **kwargs):
        return await self._request("sui_getCheckpoint", [str(block)])

    async def get_block_txes(self, block):
        checkpoint = await self.get_block(block)
        digests = checkpoint.get("transactions", [])
        if not digests:
            return []
        txes = []
        for chunk in iter_chunks(digests, SUI_MULTI_GET_CHUNK_SIZE):
            txes.extend(await self._request("sui_multiGetTransactionBlocks", [chunk, SUI_TRANSACTION_OPTIONS]))
        return txes

    def is_address(self, address):
        return isinstance(address, str) and SUI_ADDRESS_RE.fullmatch(address.lower()) is not None

    def normalize_address(self, address):
        return normalize_sui_address(address)

    async def get_payment_uri(self, address, amount, divisibility, contract=None):
        if contract:
            raise NotImplementedError("SUI token payment URIs are not implemented")
        url = f"sui:{self.normalize_address(address)}"
        amount_mist = to_wei(Decimal(amount), divisibility)
        if amount_mist:
            url += f"?amount={amount_mist}"
        return url

    async def process_tx_data(self, data):
        if not is_successful_transaction(data):
            return []
        tx_hash = self.get_tx_hash(data)
        sender = data.get("transaction", {}).get("data", {}).get("sender", "")
        transactions = []
        for change in data.get("balanceChanges", []):
            if change.get("coinType") != SUI_COIN_TYPE:
                continue
            amount = int(change.get("amount", 0))
            if amount <= 0:
                continue
            address = get_address_owner(change)
            if not address:
                continue
            transactions.append(Transaction(tx_hash, sender, self.normalize_address(address), amount))
        return transactions

    def get_tx_hash(self, tx_data):
        return tx_data["digest"]

    async def get_gas_price(self):
        return int(await self._request("suix_getReferenceGasPrice"))

    def get_wallet_key(self, xpub, contract=None, **extra_params):
        if contract:
            return f"{xpub}_{contract}"
        return xpub

    def current_server(self):
        return self.rpc.current_rpc.endpoint_uri


@dataclass
class KeyStore(BaseKeyStore):
    def load_account_from_key(self):
        try:
            self.address = daemon_ctx.get().coin.normalize_address(self.key)
        except Exception as exc:
            raise Exception("Error loading wallet: invalid address") from exc
        if not daemon_ctx.get().coin.is_address(self.address):
            raise Exception("Error loading wallet: invalid address")

    def add_privkey(self, privkey):
        raise NotImplementedError("SUI private key import is not implemented")

    @classmethod
    def load(cls, db):
        return cls(key=db.get("key", ""))

    def dump(self):
        return {"key": self.key}


@dataclass
class Wallet(BaseWallet):
    pass


class SUIDaemon(BlockProcessorDaemon):
    name = "SUI"
    BASE_SPEC_FILE = "daemons/spec/eth.json"
    DEFAULT_PORT = 5012

    DIVISIBILITY = SUI_DIVISIBILITY
    BLOCK_TIME = 1
    DEFAULT_MAX_SYNC_BLOCKS = 3600
    UNIT = "mist"

    KEYSTORE_CLASS = KeyStore
    WALLET_CLASS = Wallet

    async def create_coin(self, archive=False):
        provider = SUIRPC([SUIRPCProvider(server) for server in self.SERVER])
        await provider.start()
        self.coin = SUIFeatures(provider)

    async def shutdown_coin(self, final=False, archive_only=False):
        if hasattr(self, "coin"):
            await self.coin.rpc.stop()

    def get_default_server_url(self):
        return SUI_SERVERS.get(self.NET, SUI_SERVERS["mainnet"])

    async def load_wallet(self, xpub, contract, diskless=False, extra_params=None):
        if contract:
            raise NotImplementedError("SUI token wallets are not implemented")
        if extra_params is None:
            extra_params = {}
        wallet_key = self.coin.get_wallet_key(xpub, contract, **extra_params)
        if wallet_key in self.wallets:
            return self.wallets[wallet_key]
        if not xpub:
            return None

        wallet = self._load_wallet_storage(xpub, contract, wallet_key, diskless, extra_params)
        await self._start_wallet(wallet_key, wallet)
        return wallet

    def _load_wallet_storage(self, xpub, contract, wallet_key, diskless, extra_params):
        if diskless:
            return self.restore_wallet_from_text(xpub, contract, path=NOOP_PATH, **extra_params)
        wallet_dir = self.get_wallet_path()
        wallet_path = os.path.join(wallet_dir, wallet_key)
        if not os.path.exists(wallet_path):
            self.restore(xpub, wallet_path=wallet_path, contract=contract, **extra_params)
        storage = Storage(wallet_path)
        db = WalletDB(storage.read())
        return self.WALLET_CLASS(self.coin, db, storage)

    async def _start_wallet(self, wallet_key, wallet):
        self.wallets[wallet_key] = wallet
        self.wallets_updates[wallet_key] = deque(maxlen=self.POLLING_CAP)
        self.addresses[wallet.address].add(wallet_key)
        await wallet.start(self.latest_blocks.copy())

    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        raise NotImplementedError("SUI daemon does not support peer management")

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        params = load_json_dict(tx, "Invalid transaction")
        if not isinstance(params, list):
            raise Exception("Invalid transaction")
        return await self.coin._request("sui_executeTransactionBlock", params)

    @rpc(requires_network=True)
    async def get_default_fee(self, tx, wallet=None):
        params = load_json_dict(tx, "Invalid transaction")
        if not isinstance(params, list):
            raise Exception("Invalid transaction")
        result = await self.coin._request("sui_dryRunTransactionBlock", params)
        gas_used = result.get("effects", {}).get("gasUsed", {})
        return self._gas_summary_to_sui(gas_used)

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        return load_json_dict(tx_data, "Invalid transaction")["digest"]

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        if not isinstance(tx_data, str):
            tx_data = json.dumps(tx_data)
        return len(tx_data.encode())

    @rpc(requires_network=True)
    async def get_used_fee(self, tx_hash, wallet=None):
        data = await self.coin.get_tx_receipt(tx_hash)
        return self._gas_summary_to_sui(data.get("effects", {}).get("gasUsed", {}))

    def _gas_summary_to_sui(self, gas_used):
        return decimal_to_string(from_wei(parse_gas_used(gas_used), self.DIVISIBILITY), self.DIVISIBILITY)

    @rpc(requires_network=True)
    async def gettransaction(self, tx, wallet=None):
        data = self.coin.to_dict(await self.coin.get_transaction(tx))
        data["confirmations"] = await self.coin.get_confirmations(tx, data)
        return data

    @rpc(requires_wallet=True, requires_network=True)
    async def listaddresses(self, unused=False, funded=False, balance=False, wallet=None):
        unused, funded, balance = str_to_bool(unused), str_to_bool(funded), str_to_bool(balance)
        address = self.wallets[wallet].address
        addr_balance = await self.coin.get_balance(address)
        if (unused and addr_balance > 0) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, self.coin.to_dict(addr_balance))]
        return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", full_info=False, wallet=None):
        raise NotImplementedError("SUI wallet creation is not implemented; restore a SUI address as watch-only")

    @rpc(requires_network=True)
    async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args, **kwargs):
        raise NotImplementedError("SUI outbound transfers are not implemented")

    @rpc(requires_wallet=True)
    def signmessage(self, address=None, message=None, wallet=None):
        raise NotImplementedError("SUI message signing is not implemented")

    def _sign_transaction(self, tx, private_key):
        raise NotImplementedError("SUI transaction signing is not implemented")

    @rpc
    def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        return modify_payment_url("amount", url, to_wei(Decimal(amount), divisibility or self.DIVISIBILITY))


if __name__ == "__main__":
    SUIDaemon().start()
