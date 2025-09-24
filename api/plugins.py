import glob
import importlib
import os
from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Any, NewType, cast

from dishka import AsyncContainer as DIContainer
from dishka import FromDishka as FromDI
from dishka import Provider
from dishka import Scope as DIScope
from dishka.integrations.fastapi import DishkaRoute as DIRoute
from fastapi import FastAPI
from pydantic import TypeAdapter

from api import models
from api.logging import Logger, get_exception_message, get_logger
from api.schemas.base import Schema
from api.settings import Settings

if TYPE_CHECKING:
    from api.services.plugin_registry import PluginRegistry

SKIP_PAYMENT_METHOD = object()  # return this in your plugin if you want to skip current method creation

logger = get_logger(__name__)


def get_plugin_logger(module_name: str) -> Logger:
    parts = module_name.split(".")
    if len(parts) >= 3 and parts[0] == "modules":
        orgname = parts[1]
        clean_name = ".".join(parts[2:]) if orgname == "bitcart" else ".".join(parts[1:])
        return get_logger(clean_name)
    return get_logger(module_name)


def jsonable_encoder(obj: Any) -> Any:
    return TypeAdapter(Any).dump_python(obj, mode="json")


# Exposed public API
class PluginContext:
    def __init__(self, plugin_registry: "PluginRegistry", container: DIContainer):
        self.plugin_registry = plugin_registry
        self.container = container  # use it to query any services

    def register_settings(self, plugin_name: str, settings_class: type[Schema]) -> None:
        self.plugin_registry.register_settings(plugin_name, settings_class)

    async def get_plugin_settings(self, plugin_name: str) -> Schema | None:
        return await self.plugin_registry.get_plugin_settings(plugin_name)

    async def run_hook(self, name: str, *args: Any, **kwargs: Any) -> None:
        return await self.plugin_registry.run_hook(name, *args, **kwargs)

    async def apply_filters(self, name: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        return await self.plugin_registry.apply_filters(name, value, *args, **kwargs)

    def register_hook(self, name: str, hook: Callable[..., Any]) -> None:
        self.plugin_registry.register_hook(name, hook)

    register_filter = register_hook

    def register_event(self, name: str, params: list[str]) -> None:
        self.plugin_registry.register_event(name, params)

    def register_event_handler(self, name: str, handler: Callable[..., Any]) -> None:
        self.plugin_registry.register_event_handler(name, handler)

    async def publish_event(self, name: str, data: Schema, for_worker: bool = True) -> None:
        await self.plugin_registry.publish_event(name, data, for_worker)

    def json_encode(self, obj: Any) -> Any:
        return self.plugin_registry.json_encode(obj)

    def update_metadata(self, obj: models.RecordModel, key: str, value: Any) -> models.Model:
        return self.plugin_registry.update_metadata(obj, key, value)

    def get_metadata(self, obj: models.RecordModel, key: str, default: Any = None) -> Any:
        return self.plugin_registry.get_metadata(obj, key, default)

    def delete_metadata(self, obj: models.RecordModel, key: str) -> models.Model:
        return self.plugin_registry.delete_metadata(obj, key)

    async def get_plugin_key_by_lookup(self, lookup_name: str, lookup_org: str) -> str | None:
        return await self.plugin_registry.get_plugin_key_by_lookup(lookup_name, lookup_org)

    def add_template(self, name: str, text: str | None = None, applicable_to: str = "", *, path: str) -> None:
        self.plugin_registry.add_template(name, text, applicable_to, path=path)

    def get_plugin_data_dir(self, plugin_name: str) -> str:
        return self.plugin_registry.get_plugin_data_dir(plugin_name)


class BasePlugin(metaclass=ABCMeta):
    name: str
    lookup_name: str | None = None
    lookup_org: str | None = None

    PROVIDES: Callable[[], list[Provider]] | None = None

    path: str  # set by bitcart

    context: PluginContext

    def __init__(self, path: str) -> None:
        self.path = path
        self.license_key: str | None = None

    def _set_context(self, context: PluginContext) -> None:
        self.context = context

    @property
    def container(self) -> DIContainer:
        return self.context.container

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"

    def set_license_key(self, license_key: str) -> None:
        self.license_key = license_key

    def data_dir(self) -> str:
        """Get plugin's data directory"""
        return self.context.get_plugin_data_dir(self.name)

    @abstractmethod
    def setup_app(self, app: FastAPI) -> None:
        pass

    @abstractmethod
    async def startup(self) -> None:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass

    @abstractmethod
    async def worker_setup(self) -> None:
        pass

    def register_template(self, name: str, text: str | None = None, applicable_to: str = "") -> None:
        self.context.add_template(name, text, applicable_to, path=self.path)

    def register_settings(self, settings_class: type[Schema]) -> None:
        self.context.register_settings(self.name, settings_class)

    async def get_plugin_settings(self) -> Schema | None:
        return await self.context.get_plugin_settings(self.name)

    async def license_changed(self, license_key: str | None, license_info: dict[str, Any] | None) -> None:
        self.license_key = license_key


class CoinServer:
    def __init__(self, currency: str, xpub: str | None, **additional_data: Any) -> None:
        self.currency = currency
        self.xpub = xpub
        self.additional_data = additional_data

    async def getinfo(self) -> dict[str, Any]:
        return {"currency": self.currency, "synchronized": True}

    async def get_tokens(self) -> dict[str, Any]:
        return {}

    async def getabi(self) -> list[dict[str, Any]]:
        return []

    async def validatecontract(self, contract: str) -> bool:
        return False

    async def normalizeaddress(self, address: str) -> str:
        return address

    async def setrequestaddress(self, *args: Any, **kwargs: Any) -> bool:
        return False

    async def validateaddress(self, address: str) -> bool:
        return True

    async def modifypaymenturl(self, url: str, amount: Decimal, divisibility: int | None = None) -> str:
        return url


class BaseCoin(metaclass=ABCMeta):
    coin_name: str
    friendly_name: str
    is_eth_based = False
    additional_xpub_fields: list[str] = []
    rate_rules: str

    def __init__(self, xpub: str | None = None, **additional_data: Any) -> None:
        self.xpub = xpub
        server_cls = getattr(self, "server_cls", CoinServer)
        self.server = server_cls(self.coin_name.capitalize(), xpub, **additional_data)

    @abstractmethod
    async def validate_key(self, key: str, *args: Any, **kwargs: Any) -> bool:
        pass

    @abstractmethod
    async def balance(self) -> dict[str, Decimal]:
        pass

    @property
    async def node_id(self) -> str | None:
        return None

    async def list_channels(self) -> list[dict[str, Any]]:
        return []

    async def history(self) -> dict[str, Any]:
        return {"transactions": []}

    async def open_channel(self, *args: Any, **kwargs: Any) -> bool:
        return False

    async def close_channel(self, *args: Any, **kwargs: Any) -> bool:
        return False

    async def lnpay(self, *args: Any, **kwargs: Any) -> bool:
        return False


PluginClasses = NewType("PluginClasses", dict[str, type[BasePlugin]])
PluginObjects = NewType("PluginObjects", dict[str, BasePlugin])


# Had to be put here in order to init DI container early
def load_plugins(settings: Settings) -> tuple[PluginClasses, list[Provider]]:
    plugins_list = glob.glob("modules/**/**/plugin.py")
    _plugins: PluginClasses = cast(PluginClasses, {})
    providers: list[Provider] = []
    if settings.is_testing():
        return _plugins, providers
    for plugin in plugins_list:
        try:
            module = load_module(plugin)
            plugin_cls = module.Plugin
            plugin_cls.path = os.path.dirname(plugin)
            _plugins[plugin_cls.name] = plugin_cls
            plugin_provider = Provider()
            plugin_provider.from_context(provides=plugin_cls, scope=DIScope.APP)
            providers.append(plugin_provider)
            models_path = plugin.replace("plugin.py", "models.py")
            if os.path.exists(models_path):
                load_module(models_path)
            ioc_path = plugin.replace("plugin.py", "ioc.py")
            if os.path.exists(ioc_path) or os.path.exists(ioc_path.replace(".py", "")):  # file or package
                ioc_module = load_module(ioc_path)
                providers.extend(ioc_module.get_providers())
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin}: {get_exception_message(e)}")
    return _plugins, providers


def load_module(path: str) -> Any:
    return importlib.import_module(path.replace("/", ".").replace(".py", ""))


def init_plugins(plugin_classes: PluginClasses) -> PluginObjects:
    plugins: PluginObjects = cast(PluginObjects, {})
    for plugin_name, plugin_cls in plugin_classes.items():
        try:
            plugin_obj = plugin_cls(os.path.dirname(plugin_name))
            plugins[plugin_obj.name] = plugin_obj
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {get_exception_message(e)}")
    return plugins


def build_plugin_di_context(plugin_objects: PluginObjects) -> dict[type[BasePlugin], BasePlugin]:
    return {type(plugin_obj): plugin_obj for plugin_obj in plugin_objects.values()}


__all__ = [
    "SKIP_PAYMENT_METHOD",
    "FromDI",
    "DIContainer",
    "DIScope",
    "DIRoute",
    "PluginContext",
    "BasePlugin",
    "CoinServer",
    "BaseCoin",
]
