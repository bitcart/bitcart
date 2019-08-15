import os
from electrum.simple_config import SimpleConfig
from electrum import constants
from electrum.daemon import Daemon
from electrum.storage import WalletStorage
from electrum.wallet import Wallet
from electrum.bitcoin import address_to_scripthash
from electrum.commands import Commands
from electrum.synchronizer import Synchronizer, SynchronizerBase
from electrum.logging import configure_logging
from electrum.transaction import Transaction
from aiohttp import web
import time
from base64 import b64encode, b64decode
from decouple import AutoConfig
import inspect
import asyncio
import functools
import traceback
import threading

config = AutoConfig(search_path="conf")

LOGIN = config("LN_LOGIN", default="electrum")
PASSWORD = config("LN_PASSWORD", default="electrumz")
NET = config("LN_NETWORK", default="mainnet")
DEFAULT_CURRENCY = config("LN_FIAT_CURRENCY", default="USD")


def decode_auth(authstr):
    if not authstr:
        return None, None
    authstr = authstr.replace("Basic ", "")
    decoded_str = b64decode(authstr).decode("latin1")
    user, password = decoded_str.split(":")
    return user, password


def get_transaction(tx, wallet=None):
    fut = asyncio.run_coroutine_threadsafe(
        get_tx_async(tx), network.asyncio_loop)
    return fut.result()


async def get_tx_async(tx: str, wallet=None) -> dict:
    result = await network.interface.session.send_request(
        "blockchain.transaction.get",
        [tx, True])
    result_formatted = Transaction(result).deserialize()
    result_formatted.update({"confirmations": result.get("confirmations", 0)})
    return result_formatted


def exchange_rate(currency=DEFAULT_CURRENCY, wallet=None) -> str:
    if fx.get_currency() != currency:
        fx.set_currency(currency)
    return str(fx.exchange_rate())


def list_currencies(wallet=None) -> list:
    return fx.get_currencies(True)


def register_notify(wallet, skip):
    if not wallets_config.get(wallet):
        for i in wallets[wallet].listaddresses():
            asyncio.run_coroutine_threadsafe(notifier.watch_queue.put(i), loop)
        wallets_updates[wallet] = []
    wallets_config[wallet] = {"skip": skip}


def notify_tx(wallet):
    global wallets_updates
    updates = wallets_updates[wallet]
    wallets_updates[wallet] = []
    return updates


wallets = {}
wallets_updates = {}
wallets_config = {}
supported_methods = {"get_transaction": get_transaction,
                     "exchange_rate": exchange_rate,
                     "notify_tx": notify_tx,
                     "register_notify": register_notify,
                     "list_currencies": list_currencies}

# verbosity
VERBOSE = config("LN_DEBUG", cast=bool, default=False)
NETWORK_MAPPING = {"mainnet": constants.set_mainnet,
                   "testnet": constants.set_testnet,
                   "regtest": constants.set_regtest,
                   "simnet": constants.set_simnet}
activate_selected_network = NETWORK_MAPPING.get(NET.lower())
if not activate_selected_network:
    raise ValueError(
        f"Invalid network passed: {NET}. Valid choices are mainnet, testnet, regtest and simnet.")
# activate selected network
activate_selected_network()

electrum_config = SimpleConfig()
electrum_config.set_key("verbosity", VERBOSE)
# to enable lightning worker
electrum_config.set_key("lightning", True)
configure_logging(electrum_config)


class Notifier(SynchronizerBase):
    def __init__(self, network):
        SynchronizerBase.__init__(self, network)
        self.watched_addresses = set()
        self.watch_queue = asyncio.Queue()

    async def main(self):
        # resend existing subscriptions if we were restarted
        for addr in self.watched_addresses:
            await self._add_address(addr)
        # main loop
        while True:
            addr = await self.watch_queue.get()
            self.watched_addresses.add(addr)
            await self._add_address(addr)

    async def _on_address_status(self, addr, status):
        if not status:
            return
        for i in wallets:
            for j in wallets[i].listaddresses():
                if j == addr:
                    h = address_to_scripthash(addr)
                    result = await self.network.get_history_for_scripthash(h)
                    if wallets_config[i]["skip"]:
                        for k in result[:]:
                            if k["height"] < self.network.get_local_height(
                            ) and k["height"] > 0:
                                result.remove(k)
                    if result:
                        wallets_updates[i].append(
                            {"address": addr, "txes": result})
                    return


def start_it():
    global network, fx, loop, notifier
    thread = threading.currentThread()
    asyncio.set_event_loop(asyncio.new_event_loop())
    config = SimpleConfig()
    config.set_key("currency", DEFAULT_CURRENCY)
    config.set_key("use_exchange_rate", True)
    daemon = Daemon(config, listen_jsonrpc=False)
    network = daemon.network
    # as said in electrum daemon code, this is ugly
    config.fee_estimates = network.config.fee_estimates.copy()
    config.mempool_fees = network.config.mempool_fees.copy()
    fx = daemon.fx
    loop = asyncio.get_event_loop()
    notifier = Notifier(network)
    while thread.is_running:
        time.sleep(1)


thread = threading.Thread(target=start_it)
thread.is_running = True
thread.start()


def load_wallet(xpub):
    if xpub in wallets:
        return wallets[xpub]
    config = SimpleConfig()
    # as said in electrum daemon code, this is ugly
    config.fee_estimates = network.config.fee_estimates.copy()
    config.mempool_fees = network.config.mempool_fees.copy()
    command_runner = Commands(config, wallet=None, network=network)
    if not xpub:
        return command_runner
    # get wallet on disk
    wallet_dir = os.path.dirname(config.get_wallet_path())
    wallet_path = os.path.join(wallet_dir, xpub)
    if not os.path.exists(wallet_path):
        config.set_key('wallet_path', wallet_path)
        command_runner.restore(xpub)
    storage = WalletStorage(wallet_path)
    wallet = Wallet(storage)
    # some monkey patching here probably
    wallet.lnworker.start_network(network)
    # temporary disabled for lightning
    # wallet.start_network(network)
    command_runner.wallet = wallet
    # lightning worker
    command_runner.lnworker = wallet.lnworker
    wallets[xpub] = command_runner
    return command_runner


async def xpub_func(request):
    auth = request.headers.get("Authorization")
    user, password = decode_auth(auth)
    if not (user == LOGIN and password == PASSWORD):
        return web.json_response({"jsonrpc": "2.0", "error": {
                                 "code": -32600, "message": "Unauthorized"}, "id": None})
    if request.content_type == "application/json":
        data = await request.json()
    else:
        return web.json_response({"jsonrpc": "2.0", "error": {
                                 "code": -32600, "message": "Invalid JSON-RPC."}, "id": None})
    method = data.get("method")
    id = data.get("id", None)
    xpub = data.get("xpub")
    params = data.get("params", [])
    if not method:
        return web.json_response({"jsonrpc": "2.0", "error": {
                                 "code": -32601, "message": "Procedure not found."}, "id": id})
    try:
        wallet = load_wallet(xpub)
    except Exception:
        print(traceback.format_exc())
        if not method in supported_methods:
            return web.json_response({"jsonrpc": "2.0", "error": {
                                     "code": -32601, "message": "Error loading wallet"}, "id": id})
    custom = False
    if method in supported_methods:
        exec_method = supported_methods[method]
        custom = True
    else:
        try:
            exec_method = getattr(wallet, method)
        except AttributeError:
            return web.json_response({"jsonrpc": "2.0", "error": {
                                     "code": -32601, "message": "Procedure not found."}, "id": id})
    try:
        if custom:
            exec_method = functools.partial(exec_method, wallet=xpub)
        if isinstance(params, list):
            result = exec_method(*params)
        elif isinstance(params, dict):
            result = exec_method(**params)
    except Exception:
        return web.json_response({"jsonrpc": "2.0", "error": {
                                 "code": -32601, "message": traceback.format_exc().splitlines()[-1]}, "id": id})
    if inspect.isawaitable(result):
        result = await result
    return web.json_response(
        {"jsonrpc": "2.0", "result": result, "error": None, "id": id})


async def on_shutdown(app):
    thread.is_running = False

app = web.Application()
app.router.add_post("/", xpub_func)
app.on_shutdown.append(on_shutdown)
host = config("LN_HOST", default="0.0.0.0" if os.getenv(
    "IN_DOCKER") else "127.0.0.1")
port = config("LN_PORT", cast=int, default=5001)
web.run_app(app, host=host, port=port)
