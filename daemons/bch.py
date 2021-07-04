from btc import BTCDaemon
from utils import rpc


class BCHDaemon(BTCDaemon):
    name = "BCH"
    ASYNC_CLIENT = False
    LIGHTNING_SUPPORTED = False
    DEFAULT_PORT = 5004

    AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction", "payment_received"]
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
        "payment_received": "new_payment",
    }

    def load_electrum(self):
        import electroncash

        self.electrum = electroncash
        self.NETWORK_MAPPING = {
            "mainnet": self.electrum.networks.set_mainnet,
            "testnet": self.electrum.networks.set_testnet,
        }

    def add_wallet_to_command(self, wallet, req_method, exec_method, **kwargs):
        return exec_method

    def add_fallback_fee_estimates(self, config):
        pass

    def setup_config_and_logging(self):
        self.electrum.util.set_verbosity(self.VERBOSE)
        self.electrum_config = self.create_config()

    def register_callbacks(self):
        self.network.register_callback(self._process_events, self.AVAILABLE_EVENTS)

    def create_daemon(self):
        return self.electrum.daemon.Daemon(self.electrum_config, fd=None, is_gui=False, plugins=[], listen_jsonrpc=False)

    def create_commands(self, config):
        return self.electrum.commands.Commands(config=config, network=self.network, wallet=None)

    async def restore_wallet(self, command_runner, xpub, config, wallet_path):
        command_runner.restore(xpub, wallet_path=wallet_path)

    def create_wallet(self, storage, config):
        wallet = self.electrum.wallet.Wallet(storage)
        wallet.start_threads(self.network)
        return wallet

    def load_cmd_wallet(self, cmd, wallet, wallet_path):
        cmd.wallet = wallet

    def process_new_transaction(self, data, args):
        tx, wallet = args
        data["tx"] = tx.txid()
        return wallet

    def get_status_str(self, status):
        return self.electrum.paymentrequest.pr_tooltips[status]

    @rpc
    async def get_transaction(self, tx, wallet=None):
        result = self.network.synchronous_get(("blockchain.transaction.get", [tx, True]))
        result.update({"confirmations": result.get("confirmations", 0)})
        return result

    @rpc
    async def broadcast(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        result = self.wallets[wallet]["cmd"].broadcast(*args, **kwargs)
        return result[1]  # tx hash

    @rpc
    def recommended_fee(self, target, wallet=None) -> float:  # no fee estimation for BCH
        return 0

    def get_address_balance(self, address, wallet):
        return self.wallets[wallet]["wallet"].get_addr_balance(self.electrum.address.Address.from_string(address))


if __name__ == "__main__":
    daemon = BCHDaemon()
    daemon.start()
