import asyncio
import fnmatch
import os
import platform
import re
import sys
import traceback
import warnings

import aioredis
from bitcart import COINS, APIManager
from fastapi import HTTPException
from notifiers import all_providers, get_notifier
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings

from api.constants import GIT_REPO_URL, VERSION, WEBSITE
from api.ext.notifiers import parse_notifier_schema
from api.ext.ssh import load_ssh_settings


def ensure_exists(path):
    os.makedirs(path, exist_ok=True)


logger = None


def init_logging():
    from api.logger import get_logger

    global logger
    logger = get_logger(__name__)
    sys.excepthook = excepthook_handler(sys.excepthook)
    loop.set_exception_handler(handle_exception)


# TODO: refactor it all into OOP style, i.e. class Settings
def set_log_file(filename):
    global LOG_FILE_NAME, LOG_FILE, LOG_FILE_REGEX
    LOG_FILE_NAME = filename

    if LOG_FILE_NAME:
        LOG_FILE = os.path.join(LOG_DIR, LOG_FILE_NAME)
        filename_no_ext, _, file_extension = LOG_FILE_NAME.partition(".")
        LOG_FILE_REGEX = re.compile(fnmatch.translate(f"{filename_no_ext}*{file_extension}"))


config = Config("conf/.env")

# bitcart-related
ENABLED_CRYPTOS = config("BITCART_CRYPTOS", cast=CommaSeparatedStrings, default="btc")

# redis
REDIS_HOST = config("REDIS_HOST", default="redis://localhost")

# testing
TEST = config("TEST", cast=bool, default="pytest" in sys.modules)

# environment
DOCKER_ENV = config("IN_DOCKER", cast=bool, default=False)
LOGSERVER_HOST = "worker" if DOCKER_ENV else "localhost"
ROOT_PATH = config("BITCART_BACKEND_ROOTPATH", default="")

# database
DB_NAME = config("DB_DATABASE", default="bitcart")
DB_USER = config("DB_USER", default="postgres")
DB_PASSWORD = config("DB_PASSWORD", default="123@")
DB_HOST = config("DB_HOST", default="127.0.0.1")
DB_PORT = config("DB_PORT", default="5432")
if TEST:
    DB_NAME = "bitcart_test"

DATADIR = os.path.abspath(config("BITCART_DATADIR", default="data"))
ensure_exists(DATADIR)
IMAGES_DIR = os.path.join(DATADIR, "images")
ensure_exists(IMAGES_DIR)


# Logs

LOG_DIR = os.path.join(DATADIR, "logs")
ensure_exists(LOG_DIR)
LOG_FILE_NAME = None
LOG_FILE = None
LOG_FILE_REGEX = None
set_log_file(config("LOG_FILE", default=None))

# SSH to host

SSH_SETTINGS = load_ssh_settings(config)

# Update check

UPDATE_URL = config("UPDATE_URL", default=None)

# Tor support
TORRC_FILE = config("TORRC_FILE", default=None)

# initialize bitcart instances
cryptos = {}
crypto_settings = {}
with warnings.catch_warnings():  # to catch aiohttp warnings
    warnings.simplefilter("ignore")
    manager = APIManager({crypto.upper(): [] for crypto in ENABLED_CRYPTOS})
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
        manager.wallets[env_name][""] = cryptos[crypto]


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


async def init_db():
    from api import db

    await db.db.set_bind(db.CONNECTION_STR, min_size=1, loop=asyncio.get_event_loop())


def excepthook_handler(excepthook):
    def internal_error_handler(type_, value, tb):
        if type_ != KeyboardInterrupt:
            logger.error("\n" + "".join(traceback.format_exception(type_, value, tb)))
        return excepthook(type_, value, tb)

    return internal_error_handler


def handle_exception(loop, context):
    from api.logger import get_exception_message

    if "exception" in context:
        msg = get_exception_message(context["exception"])
    else:
        msg = context["message"]
    logger.error(msg)


def log_startup_info():
    logger.info(f"BitcartCC version: {VERSION} - {WEBSITE} - {GIT_REPO_URL}")
    logger.info(f"Python version: {sys.version}. On platform: {platform.platform()}")
    logger.info(
        f"BITCART_CRYPTOS={','.join([item for item in ENABLED_CRYPTOS])}; IN_DOCKER={DOCKER_ENV}; " f"LOG_FILE={LOG_FILE_NAME}"
    )
    logger.info(f"Successfully loaded {len(cryptos)} cryptos")
    logger.info(f"{len(notifiers)} notification providers available")
