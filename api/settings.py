import asyncio
import warnings

import dramatiq
import redis
from dramatiq.brokers.redis import RedisBroker
from nejma.layers import RedisLayer
from starlette.config import Config

from bitcart import BTC

config = Config("conf/.env")

# bitcart-related
RPC_USER = config("RPC_USER", default="electrum")
RPC_PASS = config("RPC_PASS", default="electrumz")
RPC_URL = config("RPC_URL", default="http://localhost:5000/")

# redis
REDIS_HOST = config("REDIS_HOST", default="redis://localhost")

# testing
TEST = config("TEST", cast=bool, default=False)

# database
DB_NAME = config("DB_DATABASE", default="bitcart")
DB_USER = config("DB_USER", default="postgres")
DB_PASSWORD = config("DB_PASSWORD", default="123@")
DB_HOST = config("DB_HOST", default="127.0.0.1")
DB_PORT = config("DB_PORT", default="5432")
if TEST:
    DB_NAME = "bitcart_test"

# initialize bitcart instance
with warnings.catch_warnings():  # it is supposed
    warnings.simplefilter("ignore")
    btc = BTC(RPC_URL, rpc_user=RPC_USER, rpc_pass=RPC_PASS)
# initialize redis layer
layer = RedisLayer(REDIS_HOST)
loop = asyncio.get_event_loop()


def run_sync(f):
    def wrapper(*args, **kwargs):
        return loop.run_until_complete(f(*args, **kwargs))

    return wrapper


shutdown = asyncio.Event(loop=loop)


class InitDB(dramatiq.Middleware):
    @run_sync
    async def before_worker_boot(self, broker, worker):
        from . import db

        await db.db.set_bind(db.CONNECTION_STR)

    def before_worker_shutdown(self, broker, worker):
        shutdown.set()


redis_broker = RedisBroker(connection_pool=redis.ConnectionPool.from_url(REDIS_HOST))
redis_broker.add_middleware(InitDB())
dramatiq.set_broker(redis_broker)
