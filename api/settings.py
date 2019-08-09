import warnings

from bitcart_async import BTC
from starlette.config import Config

config = Config("conf/.env")

RPC_USER = config("RPC_USER", default="electrum")
RPC_PASS = config("RPC_PASS", default="electrumz")
RPC_URL = config("RPC_URL", default="http://localhost:5000/")
REDIS_HOST = config("REDIS_HOST", default="redis://localhost")

with warnings.catch_warnings():  # it is supposed
    warnings.simplefilter("ignore")
    btc = BTC(RPC_URL, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
