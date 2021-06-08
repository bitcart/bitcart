import electroncash
from aiohttp import web
from base import BaseDaemon, rpc


class BCHDaemon(BaseDaemon):
    name = "BCH"
    electrum = electroncash
    NEW_ELECTRUM = False
    HAS_FEE_ESTIMATES = False
    ASYNC_CLIENT = False
    LIGHTNING_SUPPORTED = False
    DEFAULT_PORT = 5004
    NETWORK_MAPPING = {
        "mainnet": electrum.networks.set_mainnet,
        "testnet": electrum.networks.set_testnet,
    }
    AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction", "payment_received"]
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
        "payment_received": "new_payment",
    }

    def register_callbacks(self):
        self.network.register_callback(self._process_events, self.AVAILABLE_EVENTS)

    def configure_logging(self, electrum_config):
        self.electrum.util.set_verbosity(electrum_config.get("verbosity"))

    def create_daemon(self):
        return self.electrum.daemon.Daemon(
            self.electrum_config,
            self.electrum.daemon.get_fd_or_server(self.electrum_config)[0],
            False,
            plugins=[],
        )

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

    # bitcoin cash has different arguments passing order to new_transaction event
    def process_events(self, event, *args):
        wallet = None
        data = {}
        if event == "new_block":
            height = self.process_new_block()
            if not isinstance(height, int):
                return None, None
            data["height"] = height
        elif event == "new_transaction":
            tx, wallet = args
            data["tx"] = tx.txid()
        elif event == "new_payment":
            wallet, address, status = args
            data = {
                "address": str(address),
                "status": status,
                "status_str": self.electrum.paymentrequest.pr_tooltips[status],
            }
        else:
            return None, None
        return data, wallet

    @rpc
    async def get_transaction(self, tx, wallet=None):
        result = self.network.synchronous_get(("blockchain.transaction.get", [tx, True]))
        result.update({"confirmations": result.get("confirmations", 0)})
        return result

    @rpc
    async def payto(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        kwargs.pop("feerate", None)  # TODO: add to electron cash
        return self.wallets[wallet]["cmd"].payto(*args, **kwargs)

    @rpc
    async def paytomany(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        kwargs.pop("feerate", None)  # TODO: add to electron cash
        return self.wallets[wallet]["cmd"].paytomany(*args, **kwargs)

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


daemon = BCHDaemon()

app = web.Application()
daemon.configure_app(app)
daemon.start(app)
