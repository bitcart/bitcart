import asyncio
import functools
import inspect
import os
import traceback
from base64 import b64decode
from types import ModuleType

from aiohttp import web
from decouple import AutoConfig


def rpc(f):
    f.is_handler = True
    return f


class BaseDaemon:
    # initialize coin specific things here
    name: str
    # specify the module in subclass to use features from
    electrum: ModuleType
    # whether wallet loading by wallet_path is needed(new) or attribute setting(old)
    NEW_ELECTRUM = True
    # default port, must differ between daemons
    DEFAULT_PORT = 5000
    AVAILABLE_EVENTS: list = []
    EVENT_MAPPING: dict = {}
    NETWORK_MAPPING: dict = {}

    def __init__(self):
        # load env variables
        self.env_name = self.name.upper()
        self.config = AutoConfig(search_path="conf")
        self.LOGIN = self.config(f"{self.env_name}_LOGIN", default="electrum")
        self.PASSWORD = self.config(f"{self.env_name}_PASSWORD", default="electrumz")
        self.NET = self.config(f"{self.env_name}_NETWORK", default="mainnet")
        self.LIGHTNING = self.config(
            f"{self.env_name}_LIGHTNING", cast=bool, default=True
        )
        self.DEFAULT_CURRENCY = self.config(
            f"{self.env_name}_FIAT_CURRENCY", default="USD"
        )
        self.VERBOSE = self.config(f"{self.env_name}_DEBUG", cast=bool, default=False)
        self.HOST = self.config(
            f"{self.env_name}_HOST",
            default="0.0.0.0" if os.getenv("IN_DOCKER") else "127.0.0.1",
        )
        self.PORT = self.config(f"{self.env_name}_PORT", cast=int, default=self.DEFAULT_PORT)
        self.supported_methods = {
            func.__name__: func
            for func in (getattr(self, name) for name in dir(self))
            if getattr(func, "is_handler", False)
        }
        self.NETWORK_MAPPING = self.NETWORK_MAPPING or {
            "mainnet": self.electrum.constants.set_mainnet,
            "testnet": self.electrum.constants.set_testnet,
            "regtest": self.electrum.constants.set_regtest,
            "simnet": self.electrum.constants.set_simnet,
        }
        # activate network and configure logging
        activate_selected_network = self.NETWORK_MAPPING.get(self.NET.lower())
        if not activate_selected_network:
            raise ValueError(
                f"Invalid network passed: {self.NET}. Valid choices are {', '.join(self.NETWORK_MAPPING.keys())}."
            )
        activate_selected_network()
        electrum_config = self.electrum.simple_config.SimpleConfig()
        electrum_config.set_key("verbosity", self.VERBOSE)
        electrum_config.set_key("lightning", self.LIGHTNING)
        self.configure_logging(electrum_config)

        # initialize wallet storages
        self.wallets = {}
        self.wallets_config = {}
        self.wallets_updates = {}
        # initialize not yet created network
        self.network = None
        self.fx = None
        self.daemon = None

    def configure_logging(self, electrum_config):
        self.electrum.logging.configure_logging(electrum_config)

    async def on_startup(self, app):
        config = self.electrum.simple_config.SimpleConfig()
        config.set_key("currency", self.DEFAULT_CURRENCY)
        config.set_key("use_exchange_rate", True)
        self.daemon = self.electrum.daemon.Daemon(config, listen_jsonrpc=False)
        self.network = self.daemon.network
        self.network.register_callback(self._process_events, self.AVAILABLE_EVENTS)
        # as said in electrum daemon code, this is ugly
        config.fee_estimates = self.network.config.fee_estimates.copy()
        config.mempool_fees = self.network.config.mempool_fees.copy()
        self.fx = self.daemon.fx

    def create_commands(self, config):
        return self.electrum.commands.Commands(
            config=config, network=self.network, daemon=self.daemon
        )

    async def restore_wallet(self, command_runner, xpub, config):
        await command_runner.restore(xpub, wallet_path=config.get_wallet_path())

    def load_cmd_wallet(self, cmd, wallet, wallet_path):
        self.daemon.wallets[self.electrum.util.standardize_path(wallet_path)] = wallet

    async def load_wallet(self, xpub):
        if xpub in self.wallets:
            wallet_data = self.wallets[xpub]
            return wallet_data["wallet"], wallet_data["cmd"], wallet_data["config"]
        config = self.electrum.simple_config.SimpleConfig()
        # as said in electrum daemon code, this is ugly
        config.fee_estimates = self.network.config.fee_estimates.copy()
        config.mempool_fees = self.network.config.mempool_fees.copy()
        command_runner = self.create_commands(config)
        if not xpub:
            return None, command_runner, config
        # get wallet on disk
        wallet_dir = os.path.dirname(config.get_wallet_path())
        wallet_path = os.path.join(wallet_dir, xpub)
        if not os.path.exists(wallet_path):
            config.set_key("wallet_path", wallet_path)
            await self.restore_wallet(command_runner, xpub, config)
        storage = self.electrum.storage.WalletStorage(wallet_path)
        wallet = self.electrum.wallet.Wallet(storage)
        wallet.start_network(self.network)
        self.load_cmd_wallet(command_runner, wallet, wallet_path)
        while not wallet.is_up_to_date():
            await asyncio.sleep(0.1)
        self.wallets[xpub] = {"wallet": wallet, "cmd": command_runner, "config": config}
        self.wallets_config[xpub] = {"events": set()}
        self.wallets_updates[xpub] = []
        return wallet, command_runner, config

    def decode_auth(self, authstr):
        if not authstr:
            return None, None
        authstr = authstr.replace("Basic ", "")
        decoded_str = b64decode(authstr).decode("latin1")
        user, password = decoded_str.split(":")
        return user, password

    async def handle_request(self, request):
        auth = request.headers.get("Authorization")
        user, password = self.decode_auth(auth)
        if not (user == self.LOGIN and password == self.PASSWORD):
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Unauthorized"},
                    "id": None,
                }
            )
        if request.content_type == "application/json":
            data = await request.json()
        else:
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid JSON-RPC."},
                    "id": None,
                }
            )
        method = data.get("method")
        id = data.get("id", None)
        xpub = data.get("xpub")
        params = data.get("params", [])
        if not method:
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": "Procedure not found."},
                    "id": id,
                }
            )
        try:
            wallet, cmd, _ = await self.load_wallet(xpub)
        except Exception:
            if not method in self.supported_methods:
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": "Error loading wallet"},
                        "id": id,
                    }
                )
        custom = False
        if method in self.supported_methods:
            exec_method = self.supported_methods[method]
            custom = True
        else:
            try:
                exec_method = getattr(cmd, method)
            except AttributeError:
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "error": {"code": -32601, "message": "Procedure not found."},
                        "id": id,
                    }
                )
        try:
            if custom:
                exec_method = functools.partial(exec_method, wallet=xpub)
            else:
                if self.electrum.commands.known_commands[method].requires_wallet and self.NEW_ELECTRUM:
                    exec_method = functools.partial(
                        exec_method, wallet_path=wallet.storage.path if wallet else None
                    )
            if isinstance(params, list):
                result = exec_method(*params)
            elif isinstance(params, dict):
                result = exec_method(**params)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": traceback.format_exc().splitlines()[-1],
                    },
                    "id": id,
                }
            )
        return web.json_response(
            {"jsonrpc": "2.0", "result": result, "error": None, "id": id}
        )

    async def _process_events(self, event, *args):
        mapped_event = self.EVENT_MAPPING.get(event)
        data = {"event": mapped_event}
        try:
            data_got, wallet = await self.process_events(mapped_event, *args)
        except Exception:
            return
        if data_got is None:
            return
        data.update(data_got)
        for i in self.wallets_config:
            if mapped_event in self.wallets_config[i]["events"]:
                if not wallet or wallet == self.wallets[i]["wallet"]:
                    self.wallets_updates[i].append(data)

    @rpc
    def get_updates(self, wallet):
        updates = self.wallets_updates[wallet]
        self.wallets_updates[wallet] = []
        return updates

    @rpc
    def subscribe(self, events, wallet=None):
        self.wallets_config[wallet]["events"].update(events)

    @rpc
    def unsubscribe(self, events=None, wallet=None):
        if events is None:
            events = self.EVENT_MAPPING.keys()
        self.wallets_config[wallet]["events"] = set(
            i for i in self.wallets_config[wallet]["events"] if i not in events
        )

    @rpc
    async def get_transaction(self, tx, wallet=None):
        result = await self.network.interface.session.send_request(
            "blockchain.transaction.get", [tx, True]
        )
        result_formatted = self.electrum.transaction.Transaction(result).deserialize()
        result_formatted.update({"confirmations": result.get("confirmations", 0)})
        return result_formatted

    @rpc
    def exchange_rate(self, currency=None, wallet=None) -> str:
        if currency is None:
            currency = self.DEFAULT_CURRENCY
        if self.fx.get_currency() != currency:
            self.fx.set_currency(currency)
        return str(self.fx.exchange_rate())

    @rpc
    def list_currencies(self, wallet=None) -> list:
        return self.fx.get_currencies(True)

    @rpc
    def get_tx_size(self, raw_tx: dict, wallet=None) -> int:
        return self.electrum.transaction.Transaction(raw_tx).estimated_size()

    @rpc
    def get_default_fee(self, raw_tx:dict, wallet=None) -> float:
        config = self.electrum.simple_config.SimpleConfig()
        return config.estimate_fee(self.get_tx_size(raw_tx))
