import asyncio
import functools
import inspect
import os
import traceback
from base64 import b64decode
from types import ModuleType
from typing import Union

from aiohttp import web, ClientSession
from decouple import AutoConfig


def rpc(f):
    f.is_handler = True
    return f


class BaseDaemon:
    # initialize coin specific things here
    name: str
    # specify the module in subclass to use features from
    electrum: ModuleType
    # lightning support
    LIGHTNING_SUPPORTED = True
    # default port, must differ between daemons
    # whether client is using asyncio or is synchronous
    ASYNC_CLIENT = True
    DEFAULT_PORT = 5000
    AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction", "payment_received"]
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
        "payment_received": "new_payment",
    }
    NETWORK_MAPPING: dict = {}

    def __init__(self):
        # if client is sync, use sync _process_events
        if not self.ASYNC_CLIENT:
            self._process_events = self._process_events_sync
        # load env variables
        self.env_name = self.name.upper()
        self.config = AutoConfig(search_path="conf")
        self.LOGIN = self.config(f"{self.env_name}_LOGIN", default="electrum")
        self.PASSWORD = self.config(f"{self.env_name}_PASSWORD", default="electrumz")
        self.NET = self.config(f"{self.env_name}_NETWORK", default="mainnet")
        self.LIGHTNING = (
            self.config(f"{self.env_name}_LIGHTNING", cast=bool, default=True)
            if self.LIGHTNING_SUPPORTED
            else False
        )
        self.DEFAULT_CURRENCY = self.config(
            f"{self.env_name}_FIAT_CURRENCY", default="USD"
        )
        self.VERBOSE = self.config(f"{self.env_name}_DEBUG", cast=bool, default=False)
        self.HOST = self.config(
            f"{self.env_name}_HOST",
            default="0.0.0.0" if os.getenv("IN_DOCKER") else "127.0.0.1",
        )
        self.PORT = self.config(
            f"{self.env_name}_PORT", cast=int, default=self.DEFAULT_PORT
        )
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
        self.electrum_config = self.electrum.simple_config.SimpleConfig()
        self.copy_config_settings(self.electrum_config)
        self.configure_logging(self.electrum_config)

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

    def create_daemon(self):
        return self.electrum.daemon.Daemon(self.electrum_config, listen_jsonrpc=False)

    async def on_startup(self, app):
        self.client_session = ClientSession()
        self.daemon = self.create_daemon()
        self.network = self.daemon.network
        self.network.register_callback(self._process_events, self.AVAILABLE_EVENTS)
        self.fx = self.daemon.fx

    async def on_shutdown(self, app):
        await self.client_session.close()

    def create_commands(self, config):
        return self.electrum.commands.Commands(
            config=config, network=self.network, daemon=self.daemon
        )

    async def restore_wallet(self, command_runner, xpub, config):
        await command_runner.restore(xpub, wallet_path=config.get_wallet_path())

    def load_cmd_wallet(self, cmd, wallet, wallet_path):
        self.daemon.add_wallet(wallet)

    def create_wallet(self, storage, config):
        wallet = self.electrum.wallet.Wallet(storage, config=config)
        wallet.start_network(self.network)
        return wallet

    def copy_config_settings(self, config):
        config.set_key("verbosity", self.VERBOSE)
        config.set_key("lightning", self.LIGHTNING)
        config.set_key("currency", self.DEFAULT_CURRENCY)
        config.set_key("use_exchange_rate", True)

    async def load_wallet(self, xpub):
        config = self.electrum.simple_config.SimpleConfig()
        command_runner = self.create_commands(config)
        if not xpub:
            return None, command_runner, config
        if xpub in self.wallets:
            wallet_data = self.wallets[xpub]
            return wallet_data["wallet"], wallet_data["cmd"], wallet_data["config"]
        # get wallet on disk
        wallet_dir = os.path.dirname(config.get_wallet_path())
        wallet_path = os.path.join(wallet_dir, xpub)
        if not os.path.exists(wallet_path):
            config.set_key("wallet_path", wallet_path)
            await self.restore_wallet(command_runner, xpub, config)
        storage = self.electrum.storage.WalletStorage(wallet_path)
        wallet = self.create_wallet(storage, config)
        self.load_cmd_wallet(command_runner, wallet, wallet_path)
        while not wallet.is_up_to_date():
            await asyncio.sleep(0.1)
        self.wallets[xpub] = {"wallet": wallet, "cmd": command_runner, "config": config}
        self.wallets_config[xpub] = {"events": set(), "notification_url": None}
        self.wallets_updates[xpub] = []
        return wallet, command_runner, config

    def decode_auth(self, authstr):
        if not authstr:
            return None, None
        authstr = authstr.replace("Basic ", "")
        decoded_str = b64decode(authstr).decode("latin1")
        user, password = decoded_str.split(":")
        return user, password

    def parse_params(self, params):
        args = params
        kwargs = {}
        if isinstance(params, list):
            if len(params) > 1 and isinstance(params[-1], dict):
                kwargs = params.pop()
        elif isinstance(params, dict):
            kwargs = params
            args = ()
        return args, kwargs

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
        data = await request.json()
        method = data.get("method")
        id = data.get("id", None)
        params = data.get("params", [])
        args, kwargs = self.parse_params(params)
        xpub = kwargs.pop("xpub", None)
        if not method:
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": "Procedure not found."},
                    "id": id,
                }
            )
        try:
            wallet, cmd, config = await self.load_wallet(xpub)
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
                if self.electrum.commands.known_commands[method].requires_wallet:
                    cmd_name = self.electrum.commands.known_commands[method].name
                    need_path = cmd_name == "create" or cmd_name == "restore"
                    path = (
                        wallet.storage.path
                        if wallet
                        else (config.get_wallet_path() if need_path else None)
                    )
                    if need_path:
                        if isinstance(params, dict) and params.get("wallet_path"):
                            params["wallet_path"] = os.path.join(
                                self.electrum_config.electrum_path(),
                                "wallets",
                                params.get("wallet_path"),
                            )
                    exec_method = functools.partial(exec_method, wallet_path=path)

            result = exec_method(*args, **kwargs)
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
        return web.json_response({"jsonrpc": "2.0", "result": result, "id": id})

    async def _process_events(self, event, *args):
        mapped_event = self.EVENT_MAPPING.get(event)
        data = {"event": mapped_event}
        try:
            result = self.process_events(mapped_event, *args)
            if inspect.isawaitable(result):
                result = await result
            data_got, wallet = result
        except Exception:
            return
        if data_got is None:
            return
        data.update(data_got)
        for i in self.wallets_config:
            if mapped_event in self.wallets_config[i]["events"]:
                if not wallet or wallet == self.wallets[i]["wallet"]:
                    if self.wallets_config[i][
                        "notification_url"
                    ] and await self.send_notification(
                        data, self.wallets_config[i]["notification_url"]
                    ):
                        pass
                    else:
                        self.wallets_updates[i].append(data)

    async def send_notification(self, data, notification_url):
        try:
            await self.client_session.post(notification_url, json=data)
            return True
        except Exception:
            return False

    def _process_events_sync(self, event, *args):
        """For non-asyncio clients"""
        mapped_event = self.EVENT_MAPPING.get(event)
        data = {"event": mapped_event}
        try:
            data_got, wallet = self.process_events(mapped_event, *args)
        except Exception:
            pass
        if data_got is None:
            return
        data.update(data_got)
        for i in self.wallets_config:
            if mapped_event in self.wallets_config[i]["events"]:
                if not wallet or wallet == self.wallets[i]["wallet"]:
                    self.wallets_updates[i].append(data)

    def process_events(self, event, *args):
        """Override in your subclass if needed"""
        wallet = None
        data = {}
        if event == "new_block":
            data["height"] = self.network.get_local_height()
        elif event == "new_transaction":
            wallet, tx = args
            data["tx"] = tx.txid()
        elif event == "new_payment":
            wallet, address, status = args
            data = {
                "address": address,
                "status": status,
                "status_str": self.electrum.util.pr_tooltips[status],
            }
        else:
            return None, None
        return data, wallet

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
    def get_default_fee(self, tx: Union[dict, int], wallet=None) -> float:
        return self.electrum_config.estimate_fee(
            self.get_tx_size(tx) if isinstance(tx, dict) else tx
        )

    @rpc
    def configure_notifications(self, notification_url, wallet=None):
        self.wallets_config[wallet]["notification_url"] = notification_url

