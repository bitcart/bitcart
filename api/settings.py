import asyncio
import os
import sys
import warnings

import aioredis
import dramatiq
import redis
from bitcart import COINS
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker
from dramatiq.middleware import AgeLimit, Callbacks, Pipelines, Retries, ShutdownNotifications
from fastapi import HTTPException
from notifiers import all_providers, get_notifier
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings

from .ext.notifiers import parse_notifier_schema

config = Config("conf/.env")

# bitcart-related
ENABLED_CRYPTOS = config("BITCART_CRYPTOS", cast=CommaSeparatedStrings, default="btc")

# redis
REDIS_HOST = config("REDIS_HOST", default="redis://localhost")

# testing
TEST = config("TEST", cast=bool, default="pytest" in sys.modules)

# environment
DOCKER_ENV = config("IN_DOCKER", cast=bool, default=False)

# database
DB_NAME = config("DB_DATABASE", default="bitcart")
DB_USER = config("DB_USER", default="postgres")
DB_PASSWORD = config("DB_PASSWORD", default="123@")
DB_HOST = config("DB_HOST", default="127.0.0.1")
DB_PORT = config("DB_PORT", default="5432")
if TEST:
    DB_NAME = "bitcart_test"

# Tor support
TORRC_FILE = config("TORRC_FILE", default=None)

# initialize image dir


def create_ifn(path):
    if not os.path.exists(path):
        os.mkdir(path)


create_ifn("images")
create_ifn("images/products")

# initialize bitcart instances
cryptos = {}
crypto_settings = {}
with warnings.catch_warnings():  # it is supposed
    warnings.simplefilter("ignore")
    for crypto in ENABLED_CRYPTOS:
        env_name = crypto.upper()
        coin = COINS[env_name]
        default_url = coin.RPC_URL
        default_user = coin.RPC_USER
        default_password = coin.RPC_PASS
        _, default_host, default_port = default_url.split(":")
        default_host = default_host[2:]
        default_port = int(default_port)
        rpc_host = config(f"{env_name}_HOST", default=default_host)
        rpc_port = config(f"{env_name}_PORT", cast=int, default=default_port)
        rpc_url = f"http://{rpc_host}:{rpc_port}"
        rpc_user = config(f"{env_name}_LOGIN", default=default_user)
        rpc_password = config(f"{env_name}_PASSWORD", default=default_password)
        crypto_network = config(f"{env_name}_NETWORK", default="mainnet")
        crypto_lightning = config(f"{env_name}_LIGHTNING", cast=bool, default=False)
        crypto_settings[crypto] = {
            "credentials": {"rpc_url": rpc_url, "rpc_user": rpc_user, "rpc_pass": rpc_password},
            "network": crypto_network,
            "lightning": crypto_lightning,
        }
        cryptos[crypto] = coin(**crypto_settings[crypto]["credentials"])


def get_coin(coin, xpub=None):
    coin = coin.lower()
    if coin not in cryptos:
        raise HTTPException(422, "Unsupported currency")
    if not xpub:
        return cryptos[coin]
    return COINS[coin.upper()](xpub=xpub, **crypto_settings[coin]["credentials"])


# cache notifiers schema

notifiers = {}
for provider in all_providers():
    notifier = get_notifier(provider)
    properties = parse_notifier_schema(notifier.schema)
    required = []
    if "required" in notifier.required:
        required = notifier.required["required"]
        if "message" in required:
            required.remove("message")
    notifiers[notifier.name] = {"properties": properties, "required": required}

# initialize redis pool
loop = asyncio.get_event_loop()
redis_pool = None


async def init_redis():
    global redis_pool
    redis_pool = await aioredis.create_redis_pool(REDIS_HOST)


loop.create_task(init_redis())


def run_sync(f):
    def wrapper(*args, **kwargs):
        if not TEST:
            result = loop.run_until_complete(f(*args, **kwargs))
        else:
            result = loop.create_task(f(*args, **kwargs))
        return result

    return wrapper


shutdown = asyncio.Event(loop=loop)


async def init_db():
    from . import db

    await db.db.set_bind(db.CONNECTION_STR, min_size=1, loop=loop)


class InitDB(dramatiq.Middleware):
    def before_worker_boot(self, broker, worker):
        async def run():
            await init_db()

        loop.run_until_complete(run())

    def before_worker_shutdown(self, broker, worker):
        shutdown.set()


MIDDLEWARE = [m() for m in (AgeLimit, ShutdownNotifications, Callbacks, Pipelines, Retries)]

if TEST:
    broker = StubBroker(middleware=MIDDLEWARE)
    broker.emit_after("process_boot")
else:
    broker = RedisBroker(connection_pool=redis.ConnectionPool.from_url(REDIS_HOST), middleware=MIDDLEWARE)

broker.add_middleware(InitDB())
dramatiq.set_broker(broker)
