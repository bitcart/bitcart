#pylint: disable=no-member
import os
from electrum.simple_config import SimpleConfig
from electrum import constants
from electrum.daemon import Daemon
from electrum.storage import WalletStorage
from electrum.wallet import Wallet
from electrum.commands import Commands
from electrum.synchronizer import Synchronizer
from electrum.util import set_verbosity
from electrum.transaction import Transaction
from aiohttp import web
from base64 import b64encode, b64decode
from decouple import config

import asyncio
import traceback
import threading

LOGIN=config("DAEMON_LOGIN",default="electrum")
PASSWORD=config("DAEMON_PASSWORD",default="electrumz")

def decode_auth(authstr):
    if not authstr:
        return None,None
    authstr = authstr.replace("Basic ","")
    decoded_str = b64decode(authstr).decode("latin1")
    user, password = decoded_str.split(":")
    return user, password

def get_transaction(tx):
    fut = asyncio.run_coroutine_threadsafe(get_tx_async(tx), network.asyncio_loop)
    return fut.result()

async def get_tx_async(tx):
    result = await network.interface.session.send_request(
            "blockchain.transaction.get",
            [tx, True])
    result_formatted=Transaction(result).deserialize()
    result_formatted.update({"confirmations":result["confirmations"]})
    return result_formatted

def exchange_rate():
    return str(fx.exchange_rate())
    
wallets={}
supported_methods={"get_transaction":get_transaction, "exchange_rate":exchange_rate}

#verbosity level, uncomment for debug info
#set_verbosity(True)

def start_it():
    global network, fx
    asyncio.set_event_loop(asyncio.new_event_loop())
    config = SimpleConfig()
    config.set_key("currency","USD")
    config.set_key("use_exchange_rate", True)
    daemon = Daemon(config, listen_jsonrpc=False)
    network = daemon.network
    fx=daemon.fx
    while True:
        pass

threading.Thread(target=start_it).start()

def load_wallet(xpub):
    if xpub in wallets:
        return wallets[xpub]
    config = SimpleConfig()
    command_runner = Commands(config, wallet=None, network=network)
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
    wallets[xpub]=command_runner
    return command_runner

async def xpub_func(request):
    auth=request.headers.get("Authorization")
    user, password = decode_auth(auth)
    if not (user == LOGIN and password == PASSWORD):
        return web.json_response({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Unauthorized"}, "id": None})
    if request.content_type == "application/json":
        data=await request.json()
    else:
        return web.json_response({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid JSON-RPC."}, "id": None})
    method=data.get("method")
    id=data.get("id",None)
    xpub=data.get("xpub")
    if not xpub:
        return web.json_response({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Xpub not provided."}, "id": id})
    params=data.get("params",[])
    if not method:
        return web.json_response({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Procedure not found."}, "id": id})
    try:
        wallet=load_wallet(xpub)
    except Exception:
        return web.json_response({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Error loading wallet"}, "id": id})
    if method in supported_methods:
        exec_method=supported_methods[method]
    else:
        try:
            exec_method=getattr(wallet,method)
        except AttributeError:
            return web.json_response({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Procedure not found."}, "id": id})
    try:
        if type(params) == list:
            result=exec_method(*params)
        elif type(params) == dict:
            result=exec_method(**params)
    except Exception:
        return web.json_response({"jsonrpc": "2.0", "error": {"code": -32601, "message": traceback.format_exc().splitlines()[-1]}, "id": id})
    print(result)
    return web.json_response({"jsonrpc": "2.0", "result": result, "error":None, "id": id})

app=web.Application()
app.router.add_post("/",xpub_func)
web.run_app(app, host="0.0.0.0", port=5000)
