import glob
import importlib
import os
from abc import ABCMeta, abstractmethod
from collections import defaultdict

from fastapi import FastAPI

from alembic import command
from alembic.config import Config
from api import settings
from api.logger import get_logger
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


class PluginsManager:
    def __init__(self):
        self.plugins = {}
        self.hooks = defaultdict(list)
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


async def run_hook(name, *args, **kwargs):
    for hook in settings.settings.plugins.hooks[name]:
        try:
            await run_universal(hook, *args, **kwargs)
        except Exception as e:
            logger.error(f"Hook {name} failed: {get_exception_message(e)}")


def register_hook(name, hook):
    settings.settings.plugins.hooks[name].append(hook)
