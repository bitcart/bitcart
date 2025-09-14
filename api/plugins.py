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

from api import models
from api.logging import get_exception_message, get_logger
from api.schemas.base import Schema
from api.settings import Settings

if TYPE_CHECKING:
    from api.services.plugin_registry import PluginRegistry

SKIP_PAYMENT_METHOD = object()  # return this in your plugin if you want to skip current method creation

logger = get_logger(__name__)


# Exposed public API
class PluginContext:
    def __init__(self, plugin_registry: "PluginRegistry", container: DIContainer):
        self.plugin_registry = plugin_registry
        self.container = container  # use it to query any services

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

    async def update_metadata(self, model: type[models.RecordModel], object_id: str, key: str, value: Any) -> models.Model:
        return await self.plugin_registry.update_metadata(model, object_id, key, value)

    async def get_metadata(self, model: type[models.RecordModel], object_id: str, key: str, default: Any = None) -> Any:
        return await self.plugin_registry.get_metadata(model, object_id, key, default)

    async def delete_metadata(self, model: type[models.RecordModel], object_id: str, key: str) -> models.Model:
        return await self.plugin_registry.delete_metadata(model, object_id, key)

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

    def __init__(self, path: str, context: PluginContext) -> None:
        self.path = path
        self.context = context
        self.license_key: str | None = None

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


# Had to be put here in order to init DI container early
def load_plugins(settings: Settings) -> PluginClasses:
    plugins_list = glob.glob("modules/**/plugin.py")
    plugins_list.extend(glob.glob("modules/**/**/plugin.py"))
    _plugins: PluginClasses = cast(PluginClasses, {})
    if settings.is_testing():
        return _plugins
    for plugin in plugins_list:
        try:
            module = load_module(plugin)
            plugin_cls = module.Plugin
            plugin_cls.path = os.path.dirname(plugin)
            _plugins[plugin_cls.name] = plugin_cls
            models_path = plugin.replace("plugin.py", "models.py")
            if os.path.exists(models_path):
                load_module(models_path)
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin}: {get_exception_message(e)}")
    return _plugins


def load_module(path: str) -> Any:
    return importlib.import_module(path.replace("/", ".").replace(".py", ""))


def extract_di_providers(plugins: PluginClasses) -> list[Provider]:
    providers = []
    for plugin in plugins.values():
        if not plugin.PROVIDES:
            continue
        providers.extend(plugin.PROVIDES())
    return providers


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
