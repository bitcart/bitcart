import asyncio
import fnmatch
import json
import logging
import os
import platform
import re
import sys
import traceback
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Dict

import fido2.features
from aiohttp import ClientSession
from bitcart import COINS, APIManager
from bitcart.coin import Coin
from fastapi import HTTPException
from notifiers import all_providers, get_notifier
from pydantic import BaseSettings, Field, validator
from redis import asyncio as aioredis
from starlette.config import Config
from starlette.datastructures import CommaSeparatedStrings

from api import db
from api.constants import GIT_REPO_URL, PLUGINS_SCHEMA_URL, VERSION, WEBSITE
from api.ext.blockexplorer import EXPLORERS
from api.ext.notifiers import parse_notifier_schema
from api.ext.rpc import RPC
from api.ext.ssh import load_ssh_settings
from api.logger import configure_logserver, get_exception_message, get_logger
from api.schemes import SSHSettings
from api.templates import TemplateManager
from api.utils.files import ensure_exists

fido2.features.webauthn_json_mapping.enabled = True


class Settings(BaseSettings):
    enabled_cryptos: CommaSeparatedStrings = Field("btc", env="BITCART_CRYPTOS")
    redis_host: str = Field("redis://localhost", env="REDIS_HOST")
    test: bool = Field("pytest" in sys.modules, env="TEST")
    docker_env: bool = Field(False, env="IN_DOCKER")
    root_path: str = Field("", env="BITCART_BACKEND_ROOTPATH")
    db_name: str = Field("bitcart", env="DB_DATABASE")
    db_user: str = Field("postgres", env="DB_USER")
    db_password: str = Field("", env="DB_PASSWORD")
    db_host: str = Field("127.0.0.1", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    datadir: str = Field("data", env="BITCART_DATADIR")
    backups_dir: str = Field("data/backups", env="BITCART_BACKUPS_DIR")
    backend_plugins_dir: str = Field("modules", env="BITCART_BACKEND_PLUGINS_DIR")
    admin_plugins_dir: str = Field("data/admin_plugins", env="BITCART_ADMIN_PLUGINS_DIR")
    store_plugins_dir: str = Field("data/store_plugins", env="BITCART_STORE_PLUGINS_DIR")
    docker_plugins_dir: str = Field("data/docker_plugins", env="BITCART_DOCKER_PLUGINS_DIR")
    log_file: str = None
    log_file_name: str = Field(None, env="LOG_FILE")
    log_file_regex: re.Pattern = None
    ssh_settings: SSHSettings = None
    update_url: str = Field(None, env="UPDATE_URL")
    torrc_file: str = Field(None, env="TORRC_FILE")
    openapi_path: str = Field(None, env="OPENAPI_PATH")
    api_title: str = Field("BitcartCC", env="API_TITLE")
    cryptos: Dict[str, Coin] = None
    crypto_settings: dict = None
    manager: APIManager = None
    notifiers: dict = None
    redis_pool: aioredis.Redis = None
    config: Config = None
    logger: logging.Logger = None
    template_manager: TemplateManager = None
    plugins: list = None
    plugins_schema: dict = {}

    class Config:
        env_file = "conf/.env"

    @property
    def logserver_client_host(self) -> str:
        return "worker" if self.docker_env else "localhost"

    @property
    def logserver_host(self) -> str:
        return "0.0.0.0" if self.docker_env else "localhost"

    @property
    def images_dir(self) -> str:
        path = os.path.join(self.datadir, "images")
        ensure_exists(path)
        return path

    @property
    def products_image_dir(self) -> str:
        path = os.path.join(self.images_dir, "products")
        ensure_exists(path)
        return path

    @property
    def files_dir(self) -> str:
        path = os.path.join(self.datadir, "files")
        ensure_exists(path)
        return path

    @property
    def log_dir(self) -> str:
        path = os.path.join(self.datadir, "logs")
        ensure_exists(path)
        return path

    @property
    def plugins_dir(self) -> str:
        path = os.path.join(self.datadir, "plugins")
        ensure_exists(path)
        return path

    @property
    def connection_str(self):
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @validator("enabled_cryptos", pre=True, always=True)
    def validate_enabled_cryptos(cls, v):
        return CommaSeparatedStrings(v)

    @validator("db_name", pre=True, always=True)
    def set_db_name(cls, db, values):
        if values["test"]:
            return "bitcart_test"
        return db

    @validator("datadir", pre=True, always=True)
    def set_datadir(cls, path):
        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @validator("backups_dir", pre=True, always=True)
    def set_backups_dir(cls, path):
        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @validator("backend_plugins_dir", pre=True, always=True)
    def set_backend_plugins_dir(cls, path):
        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @validator("admin_plugins_dir", pre=True, always=True)
    def set_admin_plugins_dir(cls, path):
        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @validator("store_plugins_dir", pre=True, always=True)
    def set_store_plugins_dir(cls, path):
        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    @validator("docker_plugins_dir", pre=True, always=True)
    def set_docker_plugins_dir(cls, path):
        path = os.path.abspath(path)
        ensure_exists(path)
        return path

    def set_log_file(self, filename):
        self.log_file_name = filename

        if self.log_file_name:
            self.log_file = os.path.join(self.log_dir, self.log_file_name)
            filename_no_ext, _, file_extension = self.log_file_name.partition(".")
            self.log_file_regex = re.compile(fnmatch.translate(f"{filename_no_ext}*{file_extension}"))

    def __init__(self, **data):
        super().__init__(**data)
        self.config = Config("conf/.env")
        self.set_log_file(self.log_file_name)
        if not self.ssh_settings:
            self.ssh_settings = load_ssh_settings(self.config)
        self.load_cryptos()
        self.load_notification_providers()
        self.template_manager = TemplateManager()

    def load_plugins(self):
        from api.plugins import PluginsManager

        self.plugins = PluginsManager()

    def load_cryptos(self):
        self.cryptos = {}
        self.crypto_settings = {}
        self.manager = APIManager({crypto.upper(): [] for crypto in self.enabled_cryptos})
        for crypto in self.enabled_cryptos:
            env_name = crypto.upper()
            coin = COINS[env_name]
            default_url = coin.RPC_URL
            default_user = coin.RPC_USER
            default_password = coin.RPC_PASS
            _, default_host, default_port = default_url.split(":")
            default_host = default_host[2:]
            default_port = int(default_port)
            rpc_host = self.config(f"{env_name}_HOST", default=default_host)
            rpc_port = self.config(f"{env_name}_PORT", cast=int, default=default_port)
            rpc_url = f"http://{rpc_host}:{rpc_port}"
            rpc_user = self.config(f"{env_name}_LOGIN", default=default_user)
            rpc_password = self.config(f"{env_name}_PASSWORD", default=default_password)
            crypto_network = self.config(f"{env_name}_NETWORK", default="mainnet")
            crypto_lightning = self.config(f"{env_name}_LIGHTNING", cast=bool, default=False)
            self.crypto_settings[crypto] = {
                "credentials": {"rpc_url": rpc_url, "rpc_user": rpc_user, "rpc_pass": rpc_password},
                "network": crypto_network,
                "lightning": crypto_lightning,
            }
            self.cryptos[crypto] = coin(**self.crypto_settings[crypto]["credentials"])
            self.manager.wallets[env_name][""] = self.cryptos[crypto]

    def load_notification_providers(self):
        self.notifiers = {}
        for provider in all_providers():
            notifier = get_notifier(provider)
            properties = parse_notifier_schema(notifier.schema)
            required = []
            if "required" in notifier.required:
                required = notifier.required["required"]
                if "message" in required:
                    required.remove("message")
            self.notifiers[notifier.name] = {"properties": properties, "required": required}

    async def get_coin(self, coin, xpub=None):
        from api.plugins import apply_filters

        coin = coin.lower()
        if coin not in self.cryptos:
            raise HTTPException(422, "Unsupported currency")
        if not xpub:
            return self.cryptos[coin]
        obj = None
        if coin.upper() in COINS:
            obj = COINS[coin.upper()](xpub=xpub, **self.crypto_settings[coin]["credentials"])
        return await apply_filters("get_coin", obj, coin, xpub)

    async def get_default_explorer(self, coin):
        from api.plugins import apply_filters

        coin = coin.lower()
        if coin not in self.cryptos:
            raise HTTPException(422, "Unsupported currency")
        explorer = ""
        if coin in self.crypto_settings:
            explorer = EXPLORERS.get(coin, {}).get(self.crypto_settings[coin]["network"], "")
        return await apply_filters("get_coin_explorer", explorer, coin)

    def get_default_rpc(self, coin):
        coin = coin.lower()
        if coin not in self.cryptos:
            raise HTTPException(422, "Unsupported currency")
        if not self.cryptos[coin].is_eth_based:
            return ""
        return RPC.get(coin, {}).get(self.crypto_settings[coin]["network"], "")

    async def create_db_engine(self):
        return await db.db.set_bind(self.connection_str, min_size=1, loop=asyncio.get_running_loop())

    async def shutdown_db_engine(self):
        await db.db.pop_bind().close()

    @asynccontextmanager
    async def with_db(self):
        engine = await self.create_db_engine()
        yield engine
        await self.shutdown_db_engine()

    async def fetch_schema(self):
        schema_path = os.path.join(self.datadir, "plugins_schema.json")
        if os.path.exists(schema_path):
            with open(schema_path) as f:
                plugins_schema = json.loads(f.read())
            if plugins_schema["$id"] == PLUGINS_SCHEMA_URL:
                self.plugins_schema = plugins_schema
                return
        async with ClientSession() as session:
            async with session.get(PLUGINS_SCHEMA_URL) as resp:
                self.plugins_schema = await resp.json()
        with open(schema_path, "w") as f:
            f.write(json.dumps(self.plugins_schema))

    async def init(self):
        sys.excepthook = excepthook_handler(self, sys.excepthook)
        asyncio.get_running_loop().set_exception_handler(lambda *args, **kwargs: handle_exception(self, *args, **kwargs))
        if not self.test:
            await self.fetch_schema()
        self.redis_pool = aioredis.from_url(self.redis_host, decode_responses=True)
        await self.redis_pool.ping()
        await self.create_db_engine()

    async def post_plugin_init(self):
        from api.plugins import apply_filters, register_filter
        from api.views.cryptos import get_sats_rate

        self.cryptos = await apply_filters("get_cryptos", self.cryptos)
        register_filter("get_fiatlist", lambda s: s.union({"SATS"}))
        register_filter("get_rate", get_sats_rate)

    async def shutdown(self):
        if self.redis_pool:
            await self.redis_pool.close()
        await self.shutdown_db_engine()

    def init_logging(self, worker=True):
        if worker:
            configure_logserver(self.logserver_client_host)
        self.logger = get_logger(__name__)


def excepthook_handler(settings, excepthook):
    def internal_error_handler(type_, value, tb):
        if type_ != KeyboardInterrupt:
            settings.logger.error("\n" + "".join(traceback.format_exception(type_, value, tb)))
        return excepthook(type_, value, tb)

    return internal_error_handler


def handle_exception(settings, loop, context):
    if "exception" in context:
        msg = get_exception_message(context["exception"])
    else:
        msg = context["message"]
    settings.logger.error(msg)


def log_startup_info():
    settings = settings_ctx.get()
    settings.logger.info(f"BitcartCC version: {VERSION} - {WEBSITE} - {GIT_REPO_URL}")
    settings.logger.info(f"Python version: {sys.version}. On platform: {platform.platform()}")
    settings.logger.info(
        f"BITCART_CRYPTOS={','.join([item for item in settings.enabled_cryptos])}; IN_DOCKER={settings.docker_env}; "
        f"LOG_FILE={settings.log_file_name}"
    )
    settings.logger.info(f"Successfully loaded {len(settings.cryptos)} cryptos")
    settings.logger.info(f"{len(settings.notifiers)} notification providers available")


settings_ctx = ContextVar("settings")


def __getattr__(name):
    if name == "settings":
        return settings_ctx.get()
    raise AttributeError(f"module {__name__} has no attribute {name}")
