import glob
import importlib
import os
from abc import ABCMeta, abstractmethod
from collections import defaultdict

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from alembic import command
from alembic.config import Config
from api import events, settings, utils
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


class PluginsManager:
    def __init__(self):
        self.plugins = {}
        self.callbacks = defaultdict(list)
        plugins_list = glob.glob("plugins/**/plugin.py")
        plugins_list.extend(glob.glob("plugins/**/**/plugin.py"))
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
    await obj.update(metadata=obj.metadata).apply()
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
