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
import asyncio
import functools
import traceback
import threading

config = AutoConfig(search_path="conf")

LOGIN = config("BTC_LOGIN", default="electrum")
PASSWORD = config("BTC_PASSWORD", default="electrumz")
NET = config("BTC_NETWORK", default="mainnet")
DEFAULT_CURRENCY = config("BTC_FIAT_CURRENCY", default="USD")

# events
AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction"]
EVENT_MAPPING = {
    "blockchain_updated": "new_block",
    "new_transaction": "new_transaction"}


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


def get_updates(wallet):
    global wallets_updates
    updates = wallets_updates[wallet]
    wallets_updates[wallet] = []
    return updates


def subscribe(events, wallet=None):
    wallets_config[wallet]["events"].update(events)


def unsubscribe(events=EVENT_MAPPING.keys(), wallet=None):
    wallets_config[wallet]["events"] = set(
        i for i in wallets_config[wallet]["events"] if i not in events)


async def process_events(event, *args):
    data = {"event": EVENT_MAPPING.get(event)}
    wallet_only = False
    if event == "blockchain_updated":
        data["height"] = network.get_local_height()
    elif event == "new_transaction":
        wallet, tx = args
        wallet_only = True
        data["tx"] = tx.txid()
    else:
        return
    for i in wallets_config:
        if EVENT_MAPPING.get(event) in wallets_config[i]["events"]:
            if not wallet_only or wallet == wallets[i].wallet:
                wallets_updates[i].append(data)

wallets = {}
wallets_updates = {}
wallets_config = {}
supported_methods = {"get_transaction": get_transaction,
                     "exchange_rate": exchange_rate,
                     "get_updates": get_updates,
                     "list_currencies": list_currencies,
                     "subscribe": subscribe,
                     "unsubscribe": unsubscribe}

# verbosity
VERBOSE = config("BTC_DEBUG", cast=bool, default=False)
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
configure_logging(electrum_config)


def start_it():
    global network, fx, loop
    thread = threading.currentThread()
    asyncio.set_event_loop(asyncio.new_event_loop())
    config = SimpleConfig()
    config.set_key("currency", DEFAULT_CURRENCY)
    config.set_key("use_exchange_rate", True)
    daemon = Daemon(config, listen_jsonrpc=False)
    network = daemon.network
    network.register_callback(process_events, AVAILABLE_EVENTS)
    # as said in electrum daemon code, this is ugly
    config.fee_estimates = network.config.fee_estimates.copy()
    config.mempool_fees = network.config.mempool_fees.copy()
    fx = daemon.fx
    loop = asyncio.get_event_loop()
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
    wallet.start_network(network)
    command_runner.wallet = wallet
    wallets[xpub] = command_runner
    wallets_config[xpub] = {"events": set()}
    wallets_updates[xpub] = []
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
    return web.json_response(
        {"jsonrpc": "2.0", "result": result, "error": None, "id": id})


async def on_shutdown(app):
    thread.is_running = False

app = web.Application()
app.router.add_post("/", xpub_func)
app.on_shutdown.append(on_shutdown)
host = config("BTC_HOST", default="0.0.0.0" if os.getenv(
    "IN_DOCKER") else "127.0.0.1")
port = config("BTC_PORT", cast=int, default=5000)
web.run_app(app, host=host, port=port)
