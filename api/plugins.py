import glob
import importlib
import os
from abc import ABCMeta, abstractmethod
from collections import defaultdict

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from alembic import command
from alembic.config import Config
from api import events, models, settings, utils
from api.logger import get_logger
from api.templates import Template
from api.utils.common import run_universal
from api.utils.logging import get_exception_message

logger = get_logger(__name__)


class BasePlugin(metaclass=ABCMeta):
    name: str

    def __init__(self, path):
        self.path = path

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"

    @abstractmethod
    def setup_app(self, app: FastAPI):
        pass

    @abstractmethod
    async def startup(self):
        pass

    @abstractmethod
    async def shutdown(self):
        pass

    @abstractmethod
    async def worker_setup(self):
        pass

    def register_template(self, name, text=None, applicable_to=""):
        settings.settings.template_manager.add_template(
            Template(name, text, applicable_to, prefix=os.path.join(self.path, "templates"))
        )


class CoinServer:
    def __init__(self, currency, xpub, **additional_data):
        self.currency = currency
        self.xpub = xpub
        self.additional_data = additional_data

    async def getinfo(self):
        return {"currency": self.currency, "synchronized": True}

    async def get_tokens(self):
        return {}

    async def getabi(self):
        return []

    async def validatecontract(self, contract):
        return False

    async def normalizeaddress(self, address):
        return address

    async def setrequestaddress(self, *args, **kwargs):
        return False

    async def validateaddress(self, address):
        return True

    async def modifypaymenturl(self, url, amount, divisibility=None):
        return url


class BaseCoin(metaclass=ABCMeta):
    coin_name: str
    friendly_name: str
    is_eth_based = False
    additional_xpub_fields = []
    rate_rules: str

    def __init__(self, xpub=None, **additional_data):
        self.xpub = xpub
        server_cls = getattr(self, "server_cls", CoinServer)
        self.server = server_cls(self.coin_name.capitalize(), xpub, **additional_data)

    @abstractmethod
    async def validate_key(self, key, *args, **kwargs):
        pass

    @abstractmethod
    async def balance(self):
        pass

    @property
    async def node_id(self):
        return None

    async def list_channels(self):
        return []

    async def history(self):
        return {"transactions": []}

    async def open_channel(self, *args, **kwargs):
        return False

    async def close_channel(self, *args, **kwargs):
        return False

    async def lnpay(self, *args, **kwargs):
        return False


class PluginsManager:
    def __init__(self, test=False):
        self.plugins = {}
        self.callbacks = defaultdict(list)
        if not test:
            self.load_plugins()

    def load_plugins(self):
        plugins_list = glob.glob("modules/**/plugin.py")
        plugins_list.extend(glob.glob("modules/**/**/plugin.py"))
        for plugin in plugins_list:
            try:
                module = self.load_module(plugin)
                plugin_obj = module.Plugin(os.path.dirname(plugin))
                self.plugins[plugin_obj.name] = plugin_obj
                models_path = plugin.replace("plugin.py", "models.py")
                if os.path.exists(models_path):
                    self.load_module(models_path)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin}: {get_exception_message(e)}")

    def load_module(self, path):
        return importlib.import_module(path.replace("/", ".").replace(".py", ""))

    def run_migrations(self, plugin):
        config = Config("alembic.ini")
        config.set_main_option("plugin_name", plugin.name)
        config.set_main_option("version_locations", os.path.join(plugin.path, "versions"))
        config.set_main_option("no_logs", "true")
        command.upgrade(config, "head")

    def setup_app(self, app):
        for plugin in self.plugins.values():
            try:
                plugin.setup_app(app)
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to configure app: {get_exception_message(e)}")

    async def startup(self):
        for plugin in self.plugins.values():
            try:
                if os.path.exists(os.path.join(plugin.path, "versions")):
                    self.run_migrations(plugin)
                await plugin.startup()
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to start: {get_exception_message(e)}")
        await settings.settings.post_plugin_init()

    async def shutdown(self):
        for plugin in self.plugins.values():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to shutdown: {get_exception_message(e)}")

    async def worker_setup(self):
        for plugin in self.plugins.values():
            try:
                await plugin.worker_setup()
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to setup worker: {get_exception_message(e)}")


### Public API

SKIP_PAYMENT_METHOD = object()  # return this in your plugin if you want to skip current method creation


async def run_hook(name, *args, **kwargs):
    for hook in settings.settings.plugins.callbacks[name]:
        try:
            await run_universal(hook, *args, **kwargs)
        except Exception as e:
            logger.error(f"Hook {name} failed: {get_exception_message(e)}")


async def apply_filters(name, value, *args, **kwargs):
    for hook in settings.settings.plugins.callbacks[name]:
        try:
            value = await run_universal(hook, value, *args, **kwargs)
        except Exception as e:
            logger.error(f"Filter {name} failed: {get_exception_message(e)}")
    return value


def register_hook(name, hook):
    settings.settings.plugins.callbacks[name].append(hook)


register_filter = register_hook  # for better readability


def register_event(name, params):
    events.event_handler.add_event(name, {"params": set(params)})


def register_event_handler(name, handler):
    events.event_handler.add_handler(name, handler)


async def publish_event(name, data):
    await events.event_handler.publish(name, data)


json_encode = jsonable_encoder


async def _get_and_check_meta(model, object_id):
    if not hasattr(model, "metadata"):
        raise Exception("Model does not support metadata")
    obj = await utils.database.get_object(model, object_id, raise_exception=False)
    if obj is None:
        raise Exception("Object not found")
    return obj


async def update_metadata(model, object_id, key, value):
    obj = await _get_and_check_meta(model, object_id)
    obj.metadata[key] = value
    await obj.update(metadata=json_encode(obj.metadata)).apply()
    return obj


async def get_metadata(model, object_id, key, default=None):
    obj = await _get_and_check_meta(model, object_id)
    return obj["metadata"].get(key, default)


async def delete_metadata(model, object_id, key):
    obj = await _get_and_check_meta(model, object_id)
    if key in obj.metadata:
        del obj.metadata[key]
        await obj.update(metadata=obj.metadata).apply()
    return obj


def register_model_override(name, obj):
    from api import views

    old_model = getattr(models, name)
    for idx in range(len(utils.routing.ModelView.crud_models)):
        if utils.routing.ModelView.crud_models[idx] == old_model:
            utils.routing.ModelView.crud_models[idx] = obj
    setattr(models, name, obj)
    models.all_tables[name] = obj
    views.users.crud_routes.orm_model = obj
