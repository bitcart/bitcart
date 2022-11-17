import asyncio
import binascii
import json
import os
from dataclasses import dataclass
from datetime import datetime

from aiohttp import ClientError as AsyncClientError
from eth_account import Account
from eth_keys.datatypes import PrivateKey, PublicKey
from genericprocessor import NOOP_PATH, BlockchainFeatures, BlockProcessorDaemon
from genericprocessor import KeyStore as BaseKeyStore
from genericprocessor import Transaction as BaseTransaction
from genericprocessor import Wallet, WalletDB, daemon_ctx, from_wei, str_to_bool, to_wei
from jsonrpc import RPCProvider
from monero.numbers import from_atomic
from monero.seed import Seed
from monero.transaction import Transaction as MoneroTransaction
from storage import JSONEncoder as StorageJSONEncoder
from storage import Storage
from utils import exception_retry_middleware, load_json_dict, rpc
from web3 import Web3

MAX_FETCH_TXES = 100


def is_valid_hash(hexhash):
    try:
        bytearray.fromhex(hexhash)
        return len(hexhash) == 64
    except ValueError:
        return


class JSONEncoder(StorageJSONEncoder):
    def default(self, obj):
        if isinstance(obj, MoneroTransaction):
            return obj.__dict__
        return super().default(obj)


@dataclass
class Transaction(BaseTransaction):
    monero_tx: MoneroTransaction = None


class MoneroRPC(RPCProvider):
    @staticmethod
    def _validate_hashes(hashes):
        if any(map(lambda h: not is_valid_hash(h), hashes)):
            raise Exception("Invalid tx hash")

    async def get_transactions(self, hashes):
        self._validate_hashes(hashes)
        results = []
        for start_idx in range(0, len(hashes), MAX_FETCH_TXES):
            results.extend(await self._fetch_tx_list(hashes[start_idx : start_idx + MAX_FETCH_TXES]))
        return results

    async def _fetch_tx_list(self, hashes):
        resp = await self.raw_request(
            "get_transactions",
            txs_hashes=hashes,
            decode_as_json=True,
        )
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        txs = []
        for tx in resp.get("txs", []):
            as_json = json.loads(tx["as_json"])
            fee = as_json.get("rct_signatures", {}).get("txnFee")
            txs.append(
                MoneroTransaction(
                    hash=tx["tx_hash"],
                    fee=from_atomic(fee) if fee else None,
                    height=None if tx["in_pool"] else tx["block_height"],
                    timestamp=datetime.fromtimestamp(tx["block_timestamp"]) if "block_timestamp" in tx else None,
                    output_indices=tx["output_indices"] if "output_indices" in tx else None,
                    blob=binascii.unhexlify(tx["as_hex"]) or None,
                    json=as_json,
                )
            )
        return txs

    async def get_block(self, height):
        resp = await self.jsonrpc_request("get_block", height=height)
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        block = resp["block_header"]
        json_part = json.loads(resp["json"])
        return {
            **json_part,
            **block,
            "transactions": await self.get_transactions([block["miner_tx_hash"]] + json_part["tx_hashes"]),
        }

    async def broadcast(self, tx):
        resp = await self.raw_request("send_raw_transaction", tx_as_hex=tx)
        if resp["status"] != "OK":
            raise Exception(resp["status"])
        return resp


class XMRFeatures(BlockchainFeatures):
    rpc: MoneroRPC

    def __init__(self, rpc):
        self.rpc = rpc
        # TODO: find a list of exceptions to retry on
        # self.get_block_safe = exception_retry_middleware(self.get_block, (BlockNotFound,), daemon_ctx.get().VERBOSE)
        # self.get_tx_receipt_safe = exception_retry_middleware(
        #     self.get_tx_receipt, (TransactionNotFound,), daemon_ctx.get().VERBOSE
        # )
        self.get_block_safe = self.get_block
        self.get_tx_receipt_safe = self.get_tx_receipt

    async def get_block_number(self):
        return (await self.rpc.jsonrpc_request("get_block_count"))["count"] - 1

    def is_connected(self):
        return True

    async def get_gas_price(self):  # TODO: get_fee_estimate quantization mask?
        return 0

    async def is_syncing(self):
        return False

    async def get_transaction(self, tx):
        data = await self.rpc.get_transactions([tx])
        if not data:
            raise Exception("Transaction not found")
        return data[0]

    async def get_tx_receipt(self, tx):
        return await self.web3.eth.get_transaction_receipt(tx)

    async def get_balance(self, address):
        return from_wei(await self.web3.eth.get_balance(address))

    async def get_block(self, block, *args, **kwargs):
        return await self.rpc.get_block(block)

    async def get_block_txes(self, block):
        return (await self.get_block_safe(block))["transactions"]

    async def chain_id(self):
        return 1

    def is_address(self, address):
        return Web3.isAddress(address) or Web3.isChecksumAddress(address)

    def normalize_address(self, address):
        return Web3.toChecksumAddress(address)

    async def get_peer_list(self):
        return await self.web3.geth.admin.peers()

    async def get_payment_uri(self, req, divisibility, contract=None):
        chain_id = await self.chain_id()
        amount_wei = to_wei(req.amount, divisibility)
        if contract:
            return f"ethereum:{contract}@{chain_id}/transfer?address={req.address}&uint256={amount_wei}"
        return f"ethereum:{req.address}@{chain_id}?value={amount_wei}"

    async def process_tx_data(self, data):
        return Transaction(
            data.hash,
            None,
            None,
            monero_tx=data,
        )

    def get_tx_hash(self, tx_data):
        return tx_data.hash

    def get_wallet_key(self, xpub, *args, **kwargs):
        return xpub

    async def get_confirmations(self, tx_hash, data=None) -> int:
        data = data or await self.get_tx_receipt_safe(tx_hash)
        current_height = await self.get_block_number()
        return max(0, current_height - data.get("block_height", current_height - 1) + 1)

    def to_dict(self, obj):
        return json.loads(JSONEncoder(precision=daemon_ctx.get().DIVISIBILITY).encode(obj))


# NOTE: there are 2 types of retry middlewares installed
# This middleware handles network error and unexpected RPC failures
# For BlockNotFound and TransactionNotFound we create _safe variants where needed
async def async_http_retry_request_middleware(make_request, w3):
    return exception_retry_middleware(
        make_request,
        (AsyncClientError, TimeoutError, asyncio.TimeoutError, ValueError),
        daemon_ctx.get().VERBOSE,
    )


class KeyStore(BaseKeyStore):
    address: str = None

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
                    self.public_key = PublicKey.from_compressed_bytes(Web3.toBytes(hexstr=self.key))
                    self.address = self.public_key.to_checksum_address()
                except Exception:
                    if not daemon_ctx.get().coin.is_address(self.key):
                        raise Exception("Error loading wallet: invalid address")
                    self.address = daemon_ctx.get().coin.normalize_address(self.key)
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

    @classmethod
    def load(cls, db):
        return cls(key=db.get("key", ""), address=db.get("address", ""))

    def dump(self):
        return {"key": self.key, "address": self.address}


class XMRDaemon(BlockProcessorDaemon):
    name = "XMR"
    BASE_SPEC_FILE = "daemons/spec/eth.json"
    DEFAULT_PORT = 5011

    DIVISIBILITY = 12
    BLOCK_TIME = 60

    DEFAULT_MAX_SYNC_BLOCKS = 300  # 10 hours
    # from coingecko API
    FIAT_NAME = "monero"

    KEYSTORE_CLASS = KeyStore

    def __init__(self):
        super().__init__()
        self.synchronized = True  # TODO: remove

    def create_coin(self):
        self.coin = XMRFeatures(MoneroRPC(self.SERVER))

    def get_default_server_url(self):
        return ""

    async def load_wallet(self, xpub, contract, diskless=False):
        wallet_key = self.coin.get_wallet_key(xpub)
        if wallet_key in self.wallets:
            return self.wallets[wallet_key]
        if not xpub:
            return None

        if diskless:
            wallet = self.restore_wallet_from_text(xpub, path=NOOP_PATH)
        else:
            wallet_dir = self.get_wallet_path()
            wallet_path = os.path.join(wallet_dir, wallet_key)
            if not os.path.exists(wallet_path):
                self.restore(xpub, wallet_path=wallet_path)
            storage = Storage(wallet_path)
            db = WalletDB(storage.read())
            wallet = Wallet(self.coin, db, storage)
        self.wallets[wallet_key] = wallet
        self.wallets_updates[wallet_key] = []
        self.addresses[wallet.address].add(wallet_key)
        await wallet.start(self.latest_blocks.copy())
        return wallet

    ### Methods ###
    @rpc(requires_network=True)
    async def add_peer(self, url, wallet=None):
        raise NotImplementedError("Not supported in monero")

    @rpc(requires_network=True)
    async def broadcast(self, tx, wallet=None):
        return self.coin.to_dict(await self.coin.rpc.broadcast(tx))

    # @rpc(requires_network=True)
    # async def get_default_fee(self, tx, wallet=None):
    #     tx_dict = load_json_dict(tx, "Invalid transaction")
    #     has_modern_params = any(v in tx_dict for v in EIP1559_PARAMS)
    #     has_legacy_params = "gasPrice" in tx_dict
    #     if (
    #         (has_modern_params and has_legacy_params)
    #         or (has_modern_params and not self.EIP1559_SUPPORTED)
    #         or "gas" not in tx_dict
    #     ):
    #         raise Exception("Invalid mix of transaction fee params")
    #     if has_modern_params:
    #         base_fee = (await self.coin.get_block_safe("latest")).baseFeePerGas
    #         fee = (from_wei(tx_dict["maxPriorityFeePerGas"]) + from_wei(base_fee)) * tx_dict["gas"]
    #     else:
    #         fee = from_wei(tx_dict["gasPrice"]) * tx_dict["gas"]
    #     return self.coin.to_dict(fee)

    @rpc
    def get_tx_hash(self, tx_data, wallet=None):
        return load_json_dict(tx_data, "Invalid transaction")["tx_hash"]

    @rpc
    def get_tx_size(self, tx_data, wallet=None):
        return len(Web3.toBytes(hexstr=tx_data))

    @rpc(requires_network=True)
    async def get_tx_status(self, tx, wallet=None):
        data = self.coin.to_dict(await self.coin.get_tx_receipt_safe(tx))
        data["confirmations"] = await self.coin.get_confirmations(tx, data)
        return data

    @rpc(requires_network=True)
    async def get_used_fee(self, tx_hash, wallet=None):
        tx_stats = await self.get_tx_status(tx_hash)
        return self.coin.to_dict(tx_stats["gasUsed"] * from_wei(tx_stats["effectiveGasPrice"]))

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
        if (unused and (addr_balance > 0)) or (funded and addr_balance == 0):
            return []
        if balance:
            return [(address, self.coin.to_dict(addr_balance))]
        else:
            return [address]

    @rpc
    def make_seed(self, nbits=128, language="english", wallet=None):
        return Seed().phrase

    # @rpc(requires_wallet=True, requires_network=True)
    # async def payto(self, destination, amount, fee=None, feerate=None, gas=None, unsigned=False, wallet=None, *args,
    # **kwargs):
    #     address = self.wallets[wallet].address
    #     tx_dict = {
    #         "to": destination,
    #         "value": Web3.toWei(amount, "ether"),
    #         **(await self.get_common_payto_params(address)),
    #     }
    #     if self.EIP1559_SUPPORTED:
    #         tx_dict["type"] = "0x2"
    #     if fee:
    #         tx_dict["maxFeePerGas"] = Web3.toWei(fee, "ether")
    #     if feerate:
    #         tx_dict["maxPriorityFeePerGas"] = Web3.toWei(feerate, "gwei")
    #     tx_dict["gas"] = int(gas) if gas else await self.get_default_gas(tx_dict)
    #     if unsigned:
    #         return tx_dict
    #     if self.wallets[wallet].is_watching_only():
    #         raise Exception("This is a watching-only wallet")
    #     return self._sign_transaction(tx_dict, self.wallets[wallet].keystore.private_key)

    # @rpc(requires_wallet=True)
    # def signmessage(self, address=None, message=None, wallet=None):
    #     # Mimic electrum API
    #     if not address and not message:
    #         raise ValueError("No message specified")
    #     if not message:
    #         message = address
    #     return self.coin.to_dict(
    #         Account.sign_message(encode_defunct(text=message), private_key=self.wallets[wallet].key).signature
    #     )

    # def _sign_transaction(self, tx, private_key):
    #     if private_key is None:
    #         raise Exception("This is a watching-only wallet")
    #     tx_dict = load_json_dict(tx, "Invalid transaction")
    #     return self.coin.to_dict(Account.sign_transaction(tx_dict, private_key=private_key).rawTransaction)

    # @rpc
    # def verifymessage(self, address, signature, message, wallet=None):
    #     return self.coin.normalize_address(
    #         Account.recover_message(encode_defunct(text=message), signature=signature)
    #     ) == self.coin.normalize_address(address)


if __name__ == "__main__":
    daemon = XMRDaemon()
    daemon.start()
