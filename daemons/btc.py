import asyncio
import functools
import inspect
import os
import sys
import traceback
from types import ModuleType
from typing import Union
from urllib.parse import urlparse

from base import BaseDaemon
from utils import JsonResponse, cached, format_satoshis, rpc


class BTCDaemon(BaseDaemon):
    name = "BTC"
    BASE_SPEC_FILE = "daemons/spec/btc.json"
    DEFAULT_PORT = 5000

    # specify the module in subclass to use features from
    electrum: ModuleType
    # lightning support
    LIGHTNING_SUPPORTED = True
    # whether client is using asyncio or is synchronous
    ASYNC_CLIENT = True
    # list of events to subscribe to
    AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction", "request_status"]
    # map electrum events to bitcart's own events
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
        "request_status": "new_payment",
    }
    # lightning methods, they have special guard for wallets not supporting it
    LIGHTNING_WALLET_METHODS = [
        "add_peer",
        "nodeid",
        "add_lightning_request",
        "open_channel",
        "close_channel",
        "lnpay",
        "list_channels",
        "list_peers",
    ]
    # override if your daemon has different networks than default electrum provides
    NETWORK_MAPPING: dict = {}

    def load_electrum(self):
        import electrum

        self.electrum = electrum

    def __init__(self):
        self.load_electrum()
        super().__init__()
        self.latest_height = -1  # to avoid duplicate block notifications
        if not self.ASYNC_CLIENT:
            self._process_events = self._process_events_sync
        # activate network and configure logging
        activate_selected_network = self.NETWORK_MAPPING.get(self.NET.lower())
        if not activate_selected_network:
            raise ValueError(
                f"Invalid network passed: {self.NET}. Valid choices are" f" {', '.join(self.NETWORK_MAPPING.keys())}."
            )
        activate_selected_network()
        self.setup_config_and_logging()
        # initialize wallet storages
        self.wallets = {}
        self.wallets_updates = {}
        # initialize not yet created network
        self.loop = asyncio.get_event_loop()
        self.network = None
        self.fx = None
        self.daemon = None

    def load_env(self):
        super().load_env()
        self.DATA_PATH = self.config("DATA_PATH", default=None)
        self.LOGIN = self.config("LOGIN", default="electrum")
        self.PASSWORD = self.config("PASSWORD", default="electrumz")
        self.NET = self.config("NETWORK", default="mainnet")
        self.LIGHTNING = self.config("LIGHTNING", cast=bool, default=False) if self.LIGHTNING_SUPPORTED else False
        self.LIGHTNING_LISTEN = self.config("LIGHTNING_LISTEN", cast=str, default="") if self.LIGHTNING_SUPPORTED else ""
        self.DEFAULT_CURRENCY = self.config("FIAT_CURRENCY", default="USD")
        self.EXCHANGE = self.config(
            "FIAT_EXCHANGE",
            default=self.electrum.exchange_rate.DEFAULT_EXCHANGE,
        )
        self.VERBOSE = self.config("DEBUG", cast=bool, default=False)
        self.SERVER = self.config("SERVER", default="")
        self.ONESERVER = self.config("ONESERVER", cast=bool, default=False)
        self.PROXY_URL = self.config("PROXY_URL", default=None)
        self.NETWORK_MAPPING = self.NETWORK_MAPPING or {
            "mainnet": self.electrum.constants.set_mainnet,
            "testnet": self.electrum.constants.set_testnet,
            "regtest": self.electrum.constants.set_regtest,
            "simnet": self.electrum.constants.set_simnet,
        }

    def get_proxy_settings(self):
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
        return {"proxy": proxy}

    @property
    @cached
    def config_options(self):
        options = {
            "verbosity": self.VERBOSE,
            "lightning": self.LIGHTNING,
            "lightning_listen": self.LIGHTNING_LISTEN,
            "use_exchange": self.EXCHANGE,
            "currency": self.DEFAULT_CURRENCY,
            "server": self.SERVER,
            "oneserver": self.ONESERVER,
            "use_exchange_rate": True,
            "electrum_path": self.DATA_PATH,
            self.NET.lower(): True,
        }
        options.update(self.get_proxy_settings())
        return options

    def create_config(self):
        return self.electrum.simple_config.SimpleConfig(options=self.config_options)

    def setup_config_and_logging(self):
        self.electrum_config = self.create_config()
        self.configure_logging(self.electrum_config)

    def configure_logging(self, electrum_config):
        self.electrum.logging.configure_logging(electrum_config)

    def create_daemon(self):
        return self.electrum.daemon.Daemon(self.electrum_config, listen_jsonrpc=False)

    def register_callbacks(self):
        self.electrum.util.register_callback(self._process_events, self.AVAILABLE_EVENTS)

    async def on_startup(self, app):
        await super().on_startup(app)
        self.daemon = self.create_daemon()
        self.network = self.daemon.network
        self.register_callbacks()
        self.fx = self.daemon.fx

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

    def add_fallback_fee_estimates(self, config):
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

    # when daemon is syncing or is synced and wallet is not, prevent running commands to avoid unexpected results
    def is_still_syncing(self, wallet):
        server_height = self.network.get_server_height()
        server_lag = self.network.get_local_height() - server_height
        return (
            self.network.is_connecting()
            or self.network.is_connected()
            and (not wallet.is_up_to_date() or server_height == 0 or server_lag > 1)
        )

    async def load_wallet(self, xpub):
        if xpub in self.wallets:
            wallet_data = self.wallets[xpub]
            return wallet_data["wallet"], wallet_data["cmd"], wallet_data["config"]
        config = self.create_config()
        self.add_fallback_fee_estimates(config)
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
        while self.is_still_syncing(wallet):
            await asyncio.sleep(0.1)
        self.wallets[xpub] = {"wallet": wallet, "cmd": command_runner, "config": config}
        self.wallets_updates[xpub] = []
        return wallet, command_runner, config

    def add_wallet_to_command(self, wallet, req_method, exec_method, **kwargs):
        if self.electrum.commands.known_commands[req_method].requires_wallet:
            config = kwargs.get("config")
            cmd_name = self.electrum.commands.known_commands[req_method].name
            need_path = cmd_name in ["create", "restore"]
            path = wallet.storage.path if wallet else (config.get_wallet_path() if need_path else None)
            exec_method = functools.partial(exec_method, wallet=path)
        return exec_method

    def get_method_data(self, method, custom):
        if custom:
            return self.supported_methods[method]
        else:
            return self.electrum.commands.known_commands[method]

    async def _get_wallet(self, id, req_method, xpub):
        wallet = cmd = config = error = None
        try:
            wallet, cmd, config = await self.load_wallet(xpub)
        except Exception:
            if req_method not in self.supported_methods or self.supported_methods[req_method].requires_wallet:
                error = JsonResponse(code=-32005, error="Error loading wallet", id=id)
        return wallet, cmd, config, error

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
        wallet = kwargs.pop("wallet", None)
        if not custom:
            exec_method = self.add_wallet_to_command(wallet, req_method, exec_method, **kwargs)
        else:
            exec_method = functools.partial(exec_method, wallet=xpub)
        if self.LIGHTNING and req_method in self.LIGHTNING_WALLET_METHODS and not wallet.has_lightning:
            raise Exception("Lightning not supported in this wallet type")
        result = exec_method(*req_args, **req_kwargs)
        return await result if inspect.isawaitable(result) else result

    async def execute_method(self, id, req_method, req_args, req_kwargs):
        xpub = req_kwargs.pop("xpub", None)
        wallet, cmd, config, error = await self._get_wallet(id, req_method, xpub)
        if error:
            return error.send()
        exec_method, custom, error = await self.get_exec_method(cmd, id, req_method)
        if error:
            return error.send()
        if self.get_method_data(req_method, custom).requires_wallet and not xpub:
            return JsonResponse(code=-32000, error="Wallet not loaded", id=id).send()
        try:
            result = await self.get_exec_result(
                xpub, req_method, req_args, req_kwargs, exec_method, custom, wallet=wallet, config=config
            )
            return JsonResponse(result=result, id=id).send()
        except BaseException:
            last_line = traceback.format_exc().splitlines()[-1]
            return JsonResponse(code=self.get_error_code(last_line), error=last_line, id=id).send()

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
        for i in self.wallets:
            if not wallet or wallet == self.wallets[i]["wallet"]:
                await self.notify_websockets(data, i)
                self.wallets_updates[i].append(data)

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
        for i in self.wallets:
            if not wallet or wallet == self.wallets[i]["wallet"]:
                asyncio.run_coroutine_threadsafe(self.notify_websockets(data, i), self.loop).result()
                self.wallets_updates[i].append(data)

    def process_new_block(self):
        height = self.network.get_local_height()
        if height > self.latest_height:
            self.latest_height = height
            return height

    def process_new_transaction(self, data, args):
        wallet, tx = args
        data["tx"] = tx.txid()
        return wallet

    def get_status_str(self, status):
        return self.electrum.invoices.pr_tooltips[status]

    def process_events(self, event, *args):
        """Override in your subclass if needed"""
        wallet = None
        data = {}
        if event == "new_block":
            height = self.process_new_block()
            if not isinstance(height, int):
                return None, None
            data["height"] = height
        elif event == "new_transaction":
            wallet = self.process_new_transaction(data, args)
        elif event == "new_payment":
            wallet, address, status = args
            data = {
                "address": str(address),
                "status": status,
                "status_str": self.get_status_str(status),
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

    @rpc
    async def get_transaction(self, tx, wallet=None):
        result = await self.network.interface.session.send_request("blockchain.transaction.get", [tx, True])
        tx = self.electrum.transaction.Transaction(result["hex"])
        result = tx.to_json()
        result.update({"confirmations": result.get("confirmations", 0)})
        return result

    @rpc
    def exchange_rate(self, currency=None, wallet=None) -> str:
        if currency is None:
            currency = self.DEFAULT_CURRENCY
        if self.fx.get_currency() != currency:
            self.fx.set_currency(currency)
        return str(self.fx.exchange_rate())

    @rpc
    def list_currencies(self, wallet=None) -> list:
        return self.fx.get_currencies(False)

    @rpc
    def get_tx_size(self, raw_tx: dict, wallet=None) -> int:
        return self.electrum.transaction.Transaction(raw_tx).estimated_size()

    @rpc
    def get_default_fee(self, tx: Union[dict, int], wallet=None) -> float:
        return self.electrum_config.estimate_fee(self.get_tx_size(tx) if isinstance(tx, dict) else tx)

    @rpc
    def recommended_fee(self, target, wallet=None) -> float:
        return self.electrum_config.eta_target_to_fee(target)

    @rpc(requires_wallet=True)
    def get_invoice(self, key, wallet):
        value = self.wallets[wallet]["wallet"].get_formatted_request(key)
        if not value:
            raise Exception("Invoice not found")
        return value

    def get_address_balance(self, address, wallet):
        return self.wallets[wallet]["wallet"].get_addr_balance(address)

    @rpc(requires_wallet=True)
    def getaddressbalance_wallet(self, address, wallet):
        confirmed, unconfirmed, unmatured = map(format_satoshis, self.get_address_balance(address, wallet))
        return {"confirmed": confirmed, "unconfirmed": unconfirmed, "unmatured": unmatured}


if __name__ == "__main__":
    daemon = BTCDaemon()
    daemon.start()
