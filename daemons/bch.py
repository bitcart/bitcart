import json
import os
from collections import defaultdict
from decimal import Decimal

from btc import BTCDaemon
from logger import configure_logging
from utils import format_satoshis, format_satoshis_plain, get_exception_message, modify_payment_url, rpc

NO_HW_SIGNING_MESSAGE = "PSBT and hardware wallet signing are not supported for this coin"

with open("daemons/tokens/cashtokens.json") as f:
    CASHTOKENS = json.loads(f.read())


class BCHDaemon(BTCDaemon):
    name = "BCH"
    ASYNC_CLIENT = False
    LIGHTNING_SUPPORTED = False
    DEFAULT_PORT = 5004
    DATA_PATH_OPTION = "electron_cash_path"

    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
        "payment_received": "new_payment",
        "verified2": "verified_tx",
    }
    ALIASES = {"get_request": "getrequest"}

    def load_electrum(self):
        import electroncash

        self.electrum = electroncash
        self.NETWORK_MAPPING = {
            "mainnet": self.electrum.networks.set_mainnet,
            "testnet": self.electrum.networks.set_testnet,
            "testnet4": self.electrum.networks.set_testnet4,
            "scalenet": self.electrum.networks.set_scalenet,
            "regtest": self.electrum.networks.set_regtest,
            "chipnet": self.electrum.networks.set_chipnet,
        }
        self.ignore_token_outputs_in_bch_requests()
        self.reuse_expired_request_addresses()

    def reuse_expired_request_addresses(self):
        # electron cash keeps addresses of expired requests reserved forever, so every unpaid invoice widens the gap
        # between used addresses and external wallets stop seeing funds. Electrum reuses them, do the same
        PR_EXPIRED = self.electrum.paymentrequest.PR_EXPIRED

        # fmt: off
        def get_unused_addresses(self, *, for_change=False, frozen_ok=True, preferred=False):
            with self.lock:
                if preferred:
                    domain = (self.get_preferred_receiving_addresses() if not for_change
                              else (self.get_preferred_change_addresses() or self.get_preferred_receiving_addresses()))
                else:
                    domain = (self.get_receiving_addresses() if not for_change
                              else (self.get_change_addresses() or self.get_receiving_addresses()))
                return [addr for addr in domain
                        if not self.get_address_history(addr)
                        and (addr not in self.receive_requests or self.get_request_status(addr)[0] == PR_EXPIRED)
                        and (frozen_ok or addr not in self.frozen_addresses)
                        and (not for_change or not self.is_retired_change_addr(addr))]
        # fmt: on

        self.electrum.wallet.Abstract_Wallet.get_unused_addresses = get_unused_addresses  # TODO: submit upstream

    def ignore_token_outputs_in_bch_requests(self):
        # electron cash counts the dust BCH on token outputs towards plain requests, so a token payment to an address
        # shared with a BCH request (same seed) partially pays it, or fully pays a zero-amount one
        # fmt: off
        def get_payment_status(self, address, amount, *, tokenreq=False, category_id=None):
            local_height = self.get_local_height()
            received, sent = self.get_addr_io(address)
            payments = []
            for txo, x in received.items():
                h, v, is_cb, token_data = x
                if tokenreq:
                    if token_data and (category_id is None or token_data.id_hex == category_id):
                        v = token_data.amount
                    else:
                        continue
                elif token_data:
                    continue
                txid, n = txo.split(':')
                info = self.verified_tx.get(txid)
                if info:
                    tx_height, timestamp, pos, _block_hash = info
                    conf = max(local_height - tx_height + 1, 0)
                else:
                    conf = 0
                payments.append((conf, v, txid))
            tx_hashes = []
            vsum = 0
            amount = amount or 0
            is_paid = False
            result_conf = None
            for conf, v, tx_hash in sorted(payments, reverse=True):
                vsum += v
                tx_hashes.append(tx_hash)
                if vsum >= amount:
                    is_paid = True
                    result_conf = conf
            return is_paid, result_conf, tx_hashes
        # fmt: on

        self.electrum.wallet.Abstract_Wallet.get_payment_status = get_payment_status  # TODO: submit upstream

    def add_wallet_to_command(self, wallet, req_method, exec_method, **kwargs):
        return exec_method

    def setup_config_and_logging(self):
        self.electrum.util.set_verbosity(self.VERBOSE)
        self.electrum_config = self.create_config()
        self.copy_config_settings(self.electrum_config)
        configure_logging(debug=self.VERBOSE)

    def register_callbacks(self, callback_function):
        self.network.register_callback(callback_function, self.available_events)

    def create_daemon(self):
        daemon = self.electrum.daemon.Daemon(self.electrum_config, fd=None, is_gui=False, plugins=[], listen_jsonrpc=False)
        daemon.start()
        return daemon

    async def shutdown_daemon(self):
        if self.daemon and self.loop:
            self.daemon.stop()
            await self.loop.run_in_executor(None, self.daemon.join)

    def create_commands(self, config):
        return self.electrum.commands.Commands(config=config, network=self.network, wallet=None, daemon=self.daemon)

    def create_storage(self, path, config):
        return self.electrum.storage.WalletStorage(path)

    def get_storage_path(self, storage):
        return storage.path

    def get_wallet_dir(self, config):
        path = os.path.join(config.path, "wallets")
        self.electrum.util.make_dir(path)
        return path

    def create_wallet(self, storage, config):
        return self.electrum.wallet.Wallet(storage)

    def init_wallet(self, wallet):
        wallet.start_threads(self.network)

    def load_cmd_wallet(self, cmd, wallet):
        super().load_cmd_wallet(cmd, wallet)
        cmd.wallet = wallet

    def process_new_transaction(self, args):
        tx, wallet = args
        data = {"tx": tx.txid()}
        return data, wallet

    def process_verified_tx(self, args):
        wallet, tx_hash, height, *_ = args
        data = {
            "tx": tx_hash,
            "height": height,
        }
        return data, wallet

    def get_status_str(self, status):
        return self.electrum.paymentrequest.pr_tooltips[status]

    def _get_request(self, wallet, address):
        return wallet.get_payment_request(address, self.electrum_config)

    def _get_request_address(self, invoice):
        return invoice["address"].to_ui_string() if not invoice.get("tokenreq") else invoice["address"].to_token_string()

    def process_new_payment(self, wallet, original_address, status):
        request = self._get_request(wallet, original_address)
        final_address = self._get_request_address(request)  # used in e.g. cashtokens
        tx_hashes = self.get_tx_hashes_for_invoice(wallet, request)
        sent_amount, tx_amounts = self.get_payment_amounts(wallet, final_address, tx_hashes, request=request)
        return {
            "address": str(final_address),
            "status": status,
            "status_str": self.get_status_str(status),
            "tx_hashes": tx_hashes,
            "sent_amount": sent_amount,
            "tx_amounts": tx_amounts,
        }

    def get_tx_hashes_for_invoice(self, wallet, invoice):
        tx_hashes = wallet.get_payment_status(
            invoice["address"],
            invoice["amount"],
            tokenreq=invoice.get("tokenreq", False),
            category_id=invoice.get("category_id"),
        )[2]
        return list(dict.fromkeys(tx_hashes))

    def get_exception_message(self, e):
        return get_exception_message(e)

    def get_proxy_options(self, proxy_dict):
        return {"proxy": self.electrum.network.serialize_proxy(proxy_dict)}

    @rpc
    async def get_transaction(self, tx, wallet=None):
        result = self.network.synchronous_get(("blockchain.transaction.get", [tx, True]))
        result.update({"confirmations": result.get("confirmations", 0)})
        return result

    @rpc(requires_wallet=True)
    def payto(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        result = self.wallets[wallet]["cmd"].payto(*args, **kwargs)
        return result["hex"]

    @rpc(requires_wallet=True)
    def paytomany(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        result = self.wallets[wallet]["cmd"].paytomany(*args, **kwargs)
        return result["hex"]

    @rpc(requires_wallet=True)
    def addtransaction(self, tx, wallet):
        tx = self.electrum.transaction.Transaction(tx)
        self.wallets[wallet]["wallet"].add_transaction(tx.txid(), tx)
        self.wallets[wallet]["wallet"].add_tx_to_history(tx.txid())
        self.wallets[wallet]["wallet"].save_transactions()

    @rpc
    async def broadcast(self, *args, **kwargs):
        kwargs.pop("wallet", None)
        result = self.create_commands(config=self.electrum_config).broadcast(*args, **kwargs)
        return result[1]  # tx hash

    @rpc(requires_wallet=True, requires_network=True)
    def get_used_fee(self, tx_hash, wallet):
        tx = self.wallets[wallet]["wallet"].transactions.get(tx_hash)
        if tx is None:
            raise Exception("No such blockchain transaction")
        delta = self.wallets[wallet]["wallet"].get_wallet_delta(tx)
        return self.format_satoshis(delta.fee, wallet)

    @rpc
    async def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        return modify_payment_url("amount", url, amount)

    def get_tx_amounts(self, wallet, address, tx_hashes, request):
        tokenreq = request.get("tokenreq")
        category_id = request.get("category_id")
        amounts = defaultdict(int)
        if tx_hashes:
            received, _ = wallet.get_addr_io(self.prepare_address(address))
            for txo, x in received.items():
                _, v, _, token_data = x
                txid, _ = txo.split(":")
                if txid in tx_hashes:
                    if tokenreq and token_data and (category_id is None or token_data.id_hex == category_id):
                        amounts[txid] += token_data.amount
                    elif not tokenreq and not token_data:
                        amounts[txid] += v
        return {tx: amounts[tx] for tx in tx_hashes}

    def format_request(self, request, wallet):
        amount = request.get("amount")
        if request.get("tokenreq"):
            contract = request["category_id"]
            if contract in self.contracts:
                token_info = self.contracts[contract]
                symbol = token_info["symbol"]
                decimals = token_info["decimals"]
                request["URI"] = f"{self.electrum.networks.net.CASHADDR_PREFIX}:{request['address']}"
                amount_text = "Unknown" if amount is None else format_satoshis_plain(amount, decimal_point=decimals)
                if amount:
                    request["URI"] += f"?amount={amount_text}"
                request.pop("amount (BCH)", None)
                request[f"amount ({symbol})"] = amount_text
        elif amount:
            request["URI"] = modify_payment_url("amount", request["URI"], format_satoshis_plain(amount))
        request["tx_hashes"] = list(dict.fromkeys(request["tx_hashes"]))
        request["sent_amount"], request["tx_amounts"] = self.get_payment_amounts(
            self.wallets[wallet]["wallet"],
            self.prepare_address(request["address"]),
            request["tx_hashes"],
            request=request,
        )
        return request

    @rpc(requires_wallet=True)
    def addrequest(self, amount, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        is_token = bool(self.wallets[wallet]["contract"])
        if is_token and amount is not None:
            token_info = self.contracts[self.wallets[wallet]["contract"]]
            decimals = token_info["decimals"]
            amount = Decimal(amount) / (Decimal(10) ** Decimal(8 - decimals))  # adjust for satoshis() call in addrequest
        result = self.wallets[wallet]["cmd"].addrequest(
            amount, *args, token_request=is_token, category_id=self.wallets[wallet]["contract"], **kwargs
        )
        return self.format_request(result, wallet)

    @rpc(requires_wallet=True)
    def getrequest(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        result = self.wallets[wallet]["cmd"].getrequest(*args, **kwargs)
        return self.format_request(result, wallet)

    def prepare_address(self, address):
        if isinstance(address, str):
            return self.electrum.address.Address.from_string(address)
        return address

    def format_satoshis(self, x, wallet=None):
        if wallet and (contract := self.wallets[wallet]["contract"]) in self.contracts:
            token_info = self.contracts[contract]
            decimals = token_info["decimals"]
            return format_satoshis(x, decimal_point=decimals)
        return format_satoshis(x)

    @rpc
    def get_default_fee(self, tx: str | int, wallet=None) -> float:
        return self.format_satoshis(
            self.electrum_config.estimate_fee(self.get_tx_size(tx) if isinstance(tx, str | dict) else tx), wallet
        )

    @rpc
    def recommended_fee(self, target, wallet=None) -> float:  # no fee estimation for BCH
        return 0

    def get_address_balance(self, address, wallet):
        return self.wallets[wallet]["wallet"].get_addr_balance(self.prepare_address(address))

    @rpc(requires_wallet=True)
    def removelocaltx(self, txid, wallet):
        self.wallets[wallet]["wallet"].remove_transaction(txid)
        self.wallets[wallet]["wallet"].save_transactions()

    @rpc
    def adjustforhwsign(self, *args, **kwargs):
        raise NotImplementedError(NO_HW_SIGNING_MESSAGE)

    @rpc
    def getfingerprint(self, *args, **kwargs):
        raise NotImplementedError(NO_HW_SIGNING_MESSAGE)

    @rpc
    def finalizepsbt(self, *args, **kwargs):
        raise NotImplementedError(NO_HW_SIGNING_MESSAGE)

    @rpc
    async def getinfo(self, wallet=None):
        data = self.create_commands(config=self.electrum_config).getinfo()
        data["synchronized"] = not self.is_still_syncing()
        data["total_wallets"] = len(self.wallets)
        return data

    async def get_commands_list(self, commands):
        return commands.help()

    async def fetch_token_info(self, contract, wallet):
        md = self.electrum.token_meta.try_to_download_metadata(wallet, contract, skip_icon=True)
        if md is None:
            raise Exception("Invalid token, failed fetching BCMR metadata")
        return md.decimals, md.symbol

    @rpc(requires_network=True)
    async def readcontract(self, contract, function, *args, **kwargs):
        if function == "decimals":
            return (await self.fetch_token_info(contract, self.wallets[kwargs["wallet"]]["wallet"]))[0]
        if function == "symbol":
            return (await self.fetch_token_info(contract, self.wallets[kwargs["wallet"]]["wallet"]))[1]
        raise NotImplementedError

    @rpc
    def validatecontract(self, address, wallet=None):
        return len(address) == 64

    @rpc(requires_wallet=True)
    async def getbalance(self, wallet):
        if not self.wallets[wallet]["contract"]:
            return self.wallets[wallet]["cmd"].getbalance()
        contract = self.wallets[wallet]["contract"]
        tok_utxos = self.wallets[wallet]["wallet"].get_utxos(tokens_only=True)
        tokens = defaultdict(list)
        for utxo in tok_utxos:
            td = utxo["token_data"]
            token_id = td.id_hex
            tokens[token_id].append(utxo)
        for token_id, utxos in tokens.items():
            if token_id == contract:
                ft_amt = self.format_satoshis(sum(u["token_data"].amount for u in utxos), wallet)
                return {"confirmed": ft_amt}
        return {"confirmed": "0"}

    @staticmethod
    def get_outpoint_longname(utxo):
        return f"{utxo['prevout_hash']}:{utxo['prevout_n']}"

    @classmethod
    def dedupe_utxos(cls, utxos):
        deduped_utxos = []
        seen = set()
        seen_token_ids = set()
        for utxo in utxos:
            key = cls.get_outpoint_longname(utxo)
            td = utxo["token_data"]
            tid = td and td.id
            if key not in seen:
                seen.add(key)
                if tid:
                    seen_token_ids.add(tid)
                deduped_utxos.append(utxo)
        return deduped_utxos

    @classmethod
    def nonfrozen_token_utxos(self, utxos, wallet):
        result = []
        for utxo in utxos:
            a_frozen = "a" if wallet.is_frozen(utxo["address"]) else ""
            c_frozen = "c" if utxo.get("is_frozen_coin") else ""
            if not a_frozen and not c_frozen:
                result.append(utxo)
        return result

    async def contract_transfer(self, contract, to, amount, wallet, unsigned=False):
        spec = self.electrum.wallet.TokenSendSpec()
        spec.payto_addr = self.prepare_address(to)
        spec.change_addr = wallet.get_unused_address(for_change=True, frozen_ok=False) or wallet.dummy_address()
        spec.send_satoshis = 0
        tok_utxos = wallet.get_utxos(tokens_only=True)
        tokens = defaultdict(list)
        for utxo in tok_utxos:
            td = utxo["token_data"]
            token_id = td.id_hex
            tokens[token_id].append(utxo)
        for token_id, utxos in tokens.items():
            if token_id == contract:
                final_utxos = self.dedupe_utxos(self.nonfrozen_token_utxos(utxos, wallet))
                spec.token_utxos = {self.get_outpoint_longname(x): x for x in final_utxos}
        spec.non_token_utxos = {
            self.get_outpoint_longname(x): x for x in wallet.get_spendable_coins(None, self.electrum_config)
        }
        spec.send_fungible_amounts = {contract: int(amount)}
        spec.send_nfts = set()
        tx = wallet.make_token_send_tx(self.electrum_config, spec)
        if unsigned:
            return tx.as_dict()
        wallet.sign_transaction(tx, None)
        return await self.broadcast(tx.as_dict())

    @rpc(requires_wallet=True, requires_network=True)
    async def writecontract(self, contract, function, *args, wallet, **kwargs):
        if function == "transfer":
            to = args[0]
            amount = args[1]
            unsigned = kwargs.pop("unsigned", False)
            return await self.contract_transfer(contract, to, amount, self.wallets[wallet]["wallet"], unsigned=unsigned)
        raise NotImplementedError

    @rpc(requires_wallet=True, requires_network=True)
    async def transfer(
        self,
        address,
        to,
        value,
        *,
        wallet,
        unsigned=False,
    ):
        try:
            divisibility = await self.readcontract(address, "decimals", wallet=wallet)
            value = int(Decimal(value) * Decimal(10**divisibility))
        except Exception as e:
            raise Exception("Invalid arguments for transfer function") from e
        return await self.writecontract(address, "transfer", to, value, unsigned=unsigned, wallet=wallet)

    @rpc
    def get_tokens(self, wallet=None):
        return CASHTOKENS


if __name__ == "__main__":
    daemon = BCHDaemon()
    daemon.start()
