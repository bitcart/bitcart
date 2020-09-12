import asyncio
import functools
import inspect
import json
import os
import sys
import traceback
from base64 import b64decode
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Optional, Union
from urllib.parse import urlparse

from aiohttp import ClientSession
from aiohttp import __version__ as aiohttp_version
from aiohttp import web
from decouple import AutoConfig
from pkg_resources import parse_version

LEGACY_AIOHTTP = parse_version(aiohttp_version) < parse_version("4.0.0a0")


def rpc(f=None, requires_wallet=False):
    def wrapper(f):
        f.is_handler = True
        f.requires_wallet = bool(requires_wallet)
        return f

    if f:
        return wrapper(f)
    return wrapper


def authenticate(f):
    def wrapper(daemon, request):
        auth = request.headers.get("Authorization")
        user, password = daemon.decode_auth(auth)
        if not (user == daemon.LOGIN and password == daemon.PASSWORD):
            return JsonResponse(code=-32600, error="Unauthorized").send()
        return f(daemon, request)

    return wrapper


@dataclass
class JsonResponse:
    id: Optional[int] = None
    code: Optional[int] = None
    error: Optional[str] = None
    result: Optional[Any] = None

    def send(self):
        if self.result is not None and self.error is not None:
            raise ValueError(f"result={self.result} and error={self.error} cannot be both set")
        if self.error is not None:
            return self.send_error_response()
        else:
            return self.send_ok_response()

    def send_error_response(self):
        return web.json_response({"jsonrpc": "2.0", "error": {"code": self.code, "message": self.error}, "id": self.id})

    def send_ok_response(self):
        return web.json_response({"jsonrpc": "2.0", "result": self.result, "id": self.id})


class BaseDaemon:
    # initialize coin specific things here
    name: str
    # specify the module in subclass to use features from
    electrum: ModuleType
    # whether wallet loading by wallet_path is needed(new) or attribute setting(old)
    NEW_ELECTRUM = True
    HAS_FEE_ESTIMATES = True
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
    LIGHTNING_WALLET_METHODS = [
        "add_peer",
        "nodeid",
        "add_lightning_request",
        "open_channel",
        "close_channel",
        "lnpay",
        "list_channels",
    ]
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
            self.config(f"{self.env_name}_LIGHTNING", cast=bool, default=False) if self.LIGHTNING_SUPPORTED else False
        )
        self.LIGHTNING_LISTEN = (
            self.config(f"{self.env_name}_LIGHTNING_LISTEN", cast=str, default="") if self.LIGHTNING_SUPPORTED else ""
        )
        self.DEFAULT_CURRENCY = self.config(f"{self.env_name}_FIAT_CURRENCY", default="USD")
        self.EXCHANGE = self.config(
            f"{self.env_name}_FIAT_EXCHANGE",
            default=self.electrum.exchange_rate.DEFAULT_EXCHANGE,
        )
        self.VERBOSE = self.config(f"{self.env_name}_DEBUG", cast=bool, default=False)
        self.HOST = self.config(
            f"{self.env_name}_HOST",
            default="0.0.0.0" if os.getenv("IN_DOCKER") else "127.0.0.1",
        )
        self.PORT = self.config(f"{self.env_name}_PORT", cast=int, default=self.DEFAULT_PORT)
        self.SERVER = self.config(f"{self.env_name}_SERVER", default="")
        self.ONESERVER = self.config(f"{self.env_name}_ONESERVER", cast=bool, default=False)
        self.PROXY_URL = self.config(f"{self.env_name}_PROXY_URL", default=None)
        self.supported_methods = {
            func.__name__: func for func in (getattr(self, name) for name in dir(self)) if getattr(func, "is_handler", False)
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
                f"Invalid network passed: {self.NET}. Valid choices are" f" {', '.join(self.NETWORK_MAPPING.keys())}."
            )
        activate_selected_network()
        self.electrum_config = self.electrum.simple_config.SimpleConfig()
        self.copy_config_settings(self.electrum_config)
        self.configure_logging(self.electrum_config)
        # Load spec file
        self.spec_file = f"daemons/spec/{self.name.lower()}.json"
        if not os.path.exists(self.spec_file):
            self.spec_file = "daemons/spec/btc.json"  # fallback to btc spec
        try:
            with open(self.spec_file) as f:
                self.spec = json.loads(f.read())
        except (OSError, json.JSONDecodeError) as e:
            sys.exit(e)
        # initialize wallet storages
        self.wallets = {}
        self.wallets_config = {}
        self.wallets_updates = {}
        # initialize not yet created network
        self.loop = asyncio.get_event_loop()
        self.network = None
        self.fx = None
        self.daemon = None

    def configure_logging(self, electrum_config):
        self.electrum.logging.configure_logging(electrum_config)

    def create_daemon(self):
        return self.electrum.daemon.Daemon(self.electrum_config, listen_jsonrpc=False)

    def set_proxy(self, config):
        proxy = None
        if self.PROXY_URL:
            try:
                parsed = urlparse(self.PROXY_URL)
                proxy = {
                    "mode": str(parsed.scheme),
                    "host": str(parsed.hostname),
                    "port": str(parsed.port),
                    "user": str(parsed.username),
                    "password": str(parsed.password),
                }
                proxy = self.electrum.network.serialize_proxy(proxy)
            except Exception:
                sys.exit(f"Invalid proxy URL. Original traceback:\n{traceback.format_exc()}")
        config.set_key("proxy", proxy)

    def register_callbacks(self):
        self.electrum.util.register_callback(self._process_events, self.AVAILABLE_EVENTS)

    async def on_startup(self, app):
        self.client_session = ClientSession()
        self.daemon = self.create_daemon()
        self.network = self.daemon.network
        self.register_callbacks()
        self.fx = self.daemon.fx

    async def on_shutdown(self, app):
        await self.client_session.close()

    def create_commands(self, config):
        return self.electrum.commands.Commands(config=config, network=self.network, daemon=self.daemon)

    async def restore_wallet(self, command_runner, xpub, config, wallet_path):
        await command_runner.restore(xpub, wallet_path=wallet_path)

    def load_cmd_wallet(self, cmd, wallet, wallet_path):
        self.daemon.add_wallet(wallet)

    def create_wallet(self, storage, config):
        db = self.electrum.wallet_db.WalletDB(storage.read(), manual_upgrades=False)
        wallet = self.electrum.wallet.Wallet(db=db, storage=storage, config=config)
        if self.LIGHTNING:
            try:
                wallet.init_lightning()
                wallet = self.electrum.wallet.Wallet(db=db, storage=storage, config=config)  # to load lightning keys
                wallet.has_lightning = True
            except AssertionError:
                wallet.has_lightning = False
        wallet.start_network(self.network)
        return wallet

    def set_network_in_config(self, config):
        for network in self.NETWORK_MAPPING:
            config.set_key(network, False)
        config.set_key(self.NET.lower(), True)

    def copy_config_settings(self, config, per_wallet=False):
        self.set_network_in_config(config)
        config.path = config.electrum_path()  # to reflect network settings
        config.user_config = self.electrum.simple_config.read_user_config(config.path)  # reread config
        self.set_network_in_config(config)  # set in new config file
        config.set_key("verbosity", self.VERBOSE)
        config.set_key("lightning", self.LIGHTNING)
        config.set_key("lightning_listen", self.LIGHTNING_LISTEN)
        config.set_key("use_exchange", self.EXCHANGE)
        config.set_key("currency", self.DEFAULT_CURRENCY)
        config.set_key("server", self.SERVER)
        config.set_key("oneserver", self.ONESERVER)
        self.set_proxy(config)
        config.set_key("use_exchange_rate", True)
        if self.HAS_FEE_ESTIMATES and per_wallet:
            config.fee_estimates = self.network.config.fee_estimates.copy() or {
                25: 1000,
                10: 1000,
                5: 1000,
                2: 1000,
            }
            config.mempool_fees = self.network.config.mempool_fees.copy() or {
                25: 1000,
                10: 1000,
                5: 1000,
                2: 1000,
            }

    async def load_wallet(self, xpub):
        if xpub in self.wallets:
            wallet_data = self.wallets[xpub]
            return wallet_data["wallet"], wallet_data["cmd"], wallet_data["config"]
        config = self.electrum.simple_config.SimpleConfig()
        self.copy_config_settings(config, True)
        command_runner = self.create_commands(config)
        if not xpub:
            return None, command_runner, config

        # get wallet on disk
        wallet_dir = os.path.dirname(config.get_wallet_path())
        wallet_path = os.path.join(wallet_dir, xpub)
        if not os.path.exists(wallet_path):
            await self.restore_wallet(command_runner, xpub, config, wallet_path=wallet_path)
        storage = self.electrum.storage.WalletStorage(wallet_path)
        wallet = self.create_wallet(storage, config)
        self.load_cmd_wallet(command_runner, wallet, wallet_path)
        while (
            self.network.is_connecting() or self.network.is_connected() and not wallet.is_up_to_date()
        ):  # when daemon is syncing or is synced and wallet is not, prevent running commands to avoid unexpected results
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

    async def get_handle_request_params(self, request):
        data = await (request.json() if LEGACY_AIOHTTP else request.json(content_type=None))
        method, id, params = data.get("method"), data.get("id", None), data.get("params", [])
        error = None if method else JsonResponse(code=-32601, error="Procedure not found", id=id)
        args, kwargs = self.parse_params(params)
        return id, method, args, kwargs, error

    async def get_exec_method(self, cmd, id, req_method):
        error = None
        exec_method = None
        if req_method in self.supported_methods:
            exec_method, custom = self.supported_methods[req_method], True
        else:
            custom = False
            if hasattr(cmd, req_method):
                exec_method = getattr(cmd, req_method)
            else:
                error = JsonResponse(code=-32601, error="Procedure not found", id=id)
        return exec_method, custom, error

    async def get_exec_result(self, xpub, req_method, req_args, req_kwargs, exec_method, custom, **kwargs):
        wallet = kwargs.get("wallet")
        if custom:
            exec_method = functools.partial(exec_method, wallet=xpub)
        else:
            if self.NEW_ELECTRUM and self.electrum.commands.known_commands[req_method].requires_wallet:
                config = kwargs.get("config")
                cmd_name = self.electrum.commands.known_commands[req_method].name
                need_path = cmd_name in ["create", "restore"]
                path = wallet.storage.path if wallet else (config.get_wallet_path() if need_path else None)
                exec_method = functools.partial(exec_method, wallet=path)
        if self.LIGHTNING and req_method in self.LIGHTNING_WALLET_METHODS and not wallet.has_lightning:
            raise Exception("Lightning not supported in this wallet type")
        result = exec_method(*req_args, **req_kwargs)
        return await result if inspect.isawaitable(result) else result

    async def _get_wallet(self, id, req_method, xpub):
        wallet = cmd = config = error = None
        try:
            wallet, cmd, config = await self.load_wallet(xpub)
        except Exception:
            if req_method not in self.supported_methods or self.supported_methods[req_method].requires_wallet:
                error = JsonResponse(code=-32005, error="Error loading wallet", id=id)
        return wallet, cmd, config, error

    @authenticate
    async def handle_request(self, request):
        id, req_method, req_args, req_kwargs, error = await self.get_handle_request_params(request)
        if error:
            return error.send()
        xpub = req_kwargs.pop("xpub", None)
        wallet, cmd, config, error = await self._get_wallet(id, req_method, xpub)
        if error:
            return error.send()
        exec_method, custom, error = await self.get_exec_method(cmd, id, req_method)
        if error:
            return error.send()
        try:
            result = await self.get_exec_result(
                xpub, req_method, req_args, req_kwargs, exec_method, custom, wallet=wallet, config=config
            )
            return JsonResponse(result=result, id=id).send()
        except BaseException:
            last_line = traceback.format_exc().splitlines()[-1]
            return JsonResponse(code=self.get_error_code(last_line), error=last_line, id=id).send()

    def get_error_code(self, error):
        for error_message in self.spec["electrum_map"]:
            if error_message in error:
                return self.spec["electrum_map"][error_message]
        return -32603  # fallback

    @authenticate
    async def handle_spec(self, request):
        return web.json_response(self.spec)

    def configure_app(self, app):
        app.router.add_post("/", self.handle_request)
        app.router.add_get("/spec", self.handle_spec)
        app.on_startup.append(self.on_startup)
        app.on_shutdown.append(self.on_shutdown)

    def start(self, app):
        web.run_app(app, host=self.HOST, port=self.PORT)

    async def _process_events(self, event, *args):
        mapped_event = self.EVENT_MAPPING.get(event)
        data = {"event": mapped_event}
        data_got = None
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
                    if self.wallets_config[i]["notification_url"] and await self.send_notification(
                        data, i, self.wallets_config[i]["notification_url"]
                    ):
                        pass
                    else:
                        self.wallets_updates[i].append(data)

    async def send_notification(self, data, xpub, notification_url):
        try:
            await self.client_session.post(notification_url, json={"updates": [data], "wallet": xpub, "currency": self.name})
            return True
        except Exception:
            return False

    def _process_events_sync(self, event, *args):
        """For non-asyncio clients"""
        mapped_event = self.EVENT_MAPPING.get(event)
        data = {"event": mapped_event}
        data_got = None
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
                    if (
                        self.wallets_config[i]["notification_url"]
                        and asyncio.run_coroutine_threadsafe(
                            self.send_notification(data, i, self.wallets_config[i]["notification_url"]),
                            self.loop,
                        ).result()
                    ):
                        pass
                    else:
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
    def validatekey(self, key, wallet=None):
        return self.electrum.keystore.is_master_key(key) or self.electrum.keystore.is_seed(key)

    @rpc(requires_wallet=True)
    def get_updates(self, wallet):
        updates = self.wallets_updates[wallet]
        self.wallets_updates[wallet] = []
        return updates

    @rpc(requires_wallet=True)
    def subscribe(self, events, wallet):
        self.wallets_config[wallet]["events"].update(events)

    @rpc(requires_wallet=True)
    def unsubscribe(self, wallet, events=None):
        if events is None:
            events = self.EVENT_MAPPING.keys()
        self.wallets_config[wallet]["events"] = set(i for i in self.wallets_config[wallet]["events"] if i not in events)

    @rpc
    async def get_transaction(self, tx, wallet=None):
        result = await self.network.interface.session.send_request("blockchain.transaction.get", [tx, True])
        tx = self.electrum.transaction.Transaction(result["hex"])
        tx.deserialize()
        result_formatted = tx.to_json()
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
        return self.electrum.transaction.Transaction(raw_tx).estimated_size()  # type: ignore

    @rpc
    def get_default_fee(self, tx: Union[dict, int], wallet=None) -> float:
        return self.electrum_config.estimate_fee(self.get_tx_size(tx) if isinstance(tx, dict) else tx)

    @rpc(requires_wallet=True)
    def configure_notifications(self, notification_url, wallet):
        self.wallets_config[wallet]["notification_url"] = notification_url
