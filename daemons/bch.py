from btc import BTCDaemon
from utils import format_satoshis, get_exception_message, modify_payment_url, rpc


class BCHDaemon(BTCDaemon):
    name = "BCH"
    ASYNC_CLIENT = False
    LIGHTNING_SUPPORTED = False
    DEFAULT_PORT = 5004

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
        }

    def add_wallet_to_command(self, wallet, req_method, exec_method, **kwargs):
        return exec_method

    def setup_config_and_logging(self):
        self.electrum.util.set_verbosity(self.VERBOSE)
        self.electrum_config = self.create_config()
        self.copy_config_settings(self.electrum_config)

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
        wallet, tx_hash, height, _ = args
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
        return invoice["address"]

    def get_tx_hashes_for_invoice(self, wallet, invoice):
        return wallet.get_payment_status(invoice["address"], invoice["amount"])[2]

    def get_exception_message(self, e):
        return get_exception_message(e)

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
        return format_satoshis(delta.fee)

    @rpc
    async def modifypaymenturl(self, url, amount, divisibility=None, wallet=None):
        return modify_payment_url("amount", url, amount)

    def get_sent_amount(self, wallet, address, tx_hashes):
        sent_amount = 0
        if tx_hashes:
            received, _ = wallet.get_addr_io(address)
            for txo, x in received.items():
                _, v, _ = x
                txid, _ = txo.split(":")
                if txid in tx_hashes:
                    sent_amount += v
        return format_satoshis(sent_amount)

    @rpc(requires_wallet=True)
    def getrequest(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        result = self.wallets[wallet]["cmd"].getrequest(*args, **kwargs)
        result["sent_amount"] = self.get_sent_amount(
            self.wallets[wallet]["wallet"], self.electrum.address.Address.from_string(result["address"]), result["tx_hashes"]
        )
        return result

    @rpc
    def recommended_fee(self, target, wallet=None) -> float:  # no fee estimation for BCH
        return 0

    def get_address_balance(self, address, wallet):
        return self.wallets[wallet]["wallet"].get_addr_balance(self.electrum.address.Address.from_string(address))

    @rpc(requires_wallet=True)
    def removelocaltx(self, txid, wallet):
        self.wallets[wallet]["wallet"].remove_transaction(txid)
        self.wallets[wallet]["wallet"].save_transactions()

    @rpc
    async def getinfo(self, wallet=None):
        data = self.create_commands(config=self.electrum_config).getinfo()
        data["synchronized"] = not self.is_still_syncing()
        return data

    async def get_commands_list(self, commands):
        return commands.help()


if __name__ == "__main__":
    daemon = BCHDaemon()
    daemon.start()
