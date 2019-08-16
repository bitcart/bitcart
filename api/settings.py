import warnings

from bitcart_async import BTC
from nejma.layers import RedisLayer
from starlette.config import Config

config = Config("conf/.env")

# bitcart-related
RPC_USER = config("RPC_USER", default="electrum")
RPC_PASS = config("RPC_PASS", default="electrumz")
RPC_URL = config("RPC_URL", default="http://localhost:5000/")

# redis
REDIS_HOST = config("REDIS_HOST", default="redis://localhost")

# database
DB_NAME = config("DB_DATABASE", default="bitcart")
DB_USER = config("DB_USER", default="postgres")
DB_PASSWORD = config("DB_PASSWORD", default="123@")
DB_HOST = config("DB_HOST", default="127.0.0.1")
DB_PORT = config("DB_PORT", default="5432")

# initialize bitcart instance
with warnings.catch_warnings():  # it is supposed
    warnings.simplefilter("ignore")
    btc = BTC(RPC_URL, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
# initialize redis layer
layer = RedisLayer(REDIS_HOST)
