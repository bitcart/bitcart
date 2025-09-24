import asyncio
import os
from collections import defaultdict
from collections.abc import Callable
from typing import Any, cast

from alembic import command
from alembic.config import Config
from dishka import AsyncContainer, Scope
from fastapi import FastAPI

from api import models, templates
from api.logging import get_exception_message, get_logger
from api.plugins import BasePlugin, PluginContext, PluginObjects, jsonable_encoder
from api.schemas.base import Schema
from api.schemas.policies import PluginsState
from api.schemas.tasks import LicenseChangedMessage, PluginTaskMessage
from api.services.settings import SettingService
from api.settings import Settings
from api.templates import TemplateManager
from api.types import ClientTasksBroker, TasksBroker
from api.utils.common import run_universal

logger = get_logger(__name__)


class PluginRegistry:
    def __init__(
        self,
        settings: Settings,
        broker: TasksBroker,
        client_broker: ClientTasksBroker,
        template_manager: TemplateManager,
        plugin_objects: PluginObjects,
        container: AsyncContainer,
    ) -> None:
        self.settings = settings
        self.broker = broker
        self.client_broker = client_broker
        self.template_manager = template_manager
        self.container = container
        self._plugin_settings: dict[str, type[Schema]] = {}
        self._plugins: dict[str, BasePlugin] = plugin_objects
        self._callbacks: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._events: dict[str, dict[str, Any]] = {}
        self.init_plugins()

    def init_plugins(self) -> None:
        for plugin_obj in self._plugins.values():
            plugin_obj._set_context(PluginContext(self, self.container))

    async def start(self) -> None:
        pass

    async def set_plugin_settings_dict(self, plugin_name: str, settings: dict[str, Any]) -> tuple[bool, Schema | None]:
        """Set settings for specific plugin"""
        if plugin_name not in self._plugin_settings:
            return False, None
        settings_class = self._plugin_settings[plugin_name]
        settings_obj = settings_class(**settings)
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            await setting_service.set_setting(settings_obj, name=f"plugin:{plugin_name}")
        await self.run_hook(f"settings_changed:{plugin_name}", settings_obj)
        return True, settings_obj

    def get_registered_plugins(self) -> list[str]:
        """Get list of plugins that have registered settings"""
        return list(self._plugin_settings.keys())

    def run_migrations(self, plugin: BasePlugin) -> None:
        config = Config("alembic.ini")
        config.set_main_option("plugin_name", plugin.name)
        config.set_main_option("version_locations", os.path.join(plugin.path, "versions"))
        config.set_main_option("no_logs", "true")
        command.upgrade(config, "head")

    def setup_app(self, app: FastAPI) -> None:
        for plugin in self._plugins.values():
            try:
                plugin.setup_app(app)
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to configure app: {get_exception_message(e)}")

    async def startup(self) -> None:
        self.register_hook("license_changed", self.handle_license_changed)
        for plugin in self._plugins.values():
            try:
                if os.path.exists(os.path.join(plugin.path, "versions")):
                    self.run_migrations(plugin)
                if plugin.lookup_name and plugin.lookup_org:
                    plugin.set_license_key(
                        cast(str, await self.get_plugin_key_by_lookup(plugin.lookup_name, plugin.lookup_org))
                    )
                await plugin.startup()
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to start: {get_exception_message(e)}")
        await self.post_plugin_init()

    async def shutdown(self) -> None:
        for plugin in self._plugins.values():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to shutdown: {get_exception_message(e)}")

    async def worker_setup(self) -> None:
        for plugin in self._plugins.values():
            try:
                await plugin.worker_setup()
            except Exception as e:
                logger.error(f"Plugin {plugin} failed to setup worker: {get_exception_message(e)}")

    async def handle_license_changed(self, license_key: str | None, license_info: dict[str, Any]) -> None:
        if not self.settings.IS_WORKER:
            await self.broker.publish(
                "license_changed", LicenseChangedMessage(license_key=license_key, license_info=license_info)
            )
            return
        for plugin in self._plugins.values():
            if (
                getattr(plugin, "lookup_name", None) == license_info["plugin_name"]
                and getattr(plugin, "lookup_org", None) == license_info["plugin_author"]
            ):
                await plugin.license_changed(license_key, license_info)

    async def post_plugin_init(self) -> None:
        from api.services.coins import CoinService

        coin_service = await self.container.get(CoinService)
        coin_service._cryptos = await self.apply_filters("get_cryptos", coin_service.cryptos)  # TODO: make it better
        self.register_filter("get_fiatlist", lambda s: s.union({"SATS"}))

    # Plugin API implementation

    def register_settings(self, plugin_name: str, settings_class: type[Schema]) -> None:
        """Register plugin settings class"""
        self._plugin_settings[plugin_name] = settings_class

    async def get_plugin_settings(self, plugin_name: str) -> Schema | None:
        """Get settings for specific plugin"""
        if plugin_name not in self._plugin_settings:
            return None
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            return await setting_service.get_setting(self._plugin_settings[plugin_name], name=f"plugin:{plugin_name}")

    async def run_hook(self, name: str, *args: Any, **kwargs: Any) -> None:
        for hook in self._callbacks[name]:
            try:
                await run_universal(hook, *args, **kwargs)
            except Exception as e:
                logger.error(f"Hook {name} failed: {get_exception_message(e)}")

    async def apply_filters(self, name: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        for hook in self._callbacks[name]:
            try:
                value = await run_universal(hook, value, *args, **kwargs)
            except Exception as e:
                logger.error(f"Filter {name} failed: {get_exception_message(e)}")
        return value

    def register_hook(self, name: str, hook: Callable[..., Any]) -> None:
        self._callbacks[name].append(hook)

    register_filter = register_hook  # for better readability

    @staticmethod
    def json_encode(obj: Any) -> Any:
        return jsonable_encoder(obj)

    def register_event(self, name: str, params: list[str]) -> None:
        self._events[name] = {"params": set(params), "handlers": []}

    def register_event_handler(self, name: str, handler: Callable[..., Any]) -> None:
        if name not in self._events:
            return
        self._events[name]["handlers"].append(handler)

    async def publish_event(self, name: str, data: Schema, for_worker: bool = True) -> None:
        await self.broker.publish(
            "plugin_task_server", PluginTaskMessage(event=name, data=data.model_dump(), for_worker=for_worker)
        )
        await self.client_broker.publish(
            "plugin_task_client", PluginTaskMessage(event=name, data=data.model_dump(), for_worker=for_worker)
        )

    def update_metadata(self, obj: models.RecordModel, key: str, value: Any) -> models.Model:
        obj.meta[key] = value
        return obj

    def get_metadata(self, obj: models.RecordModel, key: str, default: Any = None) -> Any:
        return obj.meta.get(key, default)

    def delete_metadata(self, obj: models.RecordModel, key: str) -> models.Model:
        if key in obj.meta:
            del obj.meta[key]
        return obj

    async def get_plugin_key_by_lookup(self, lookup_name: str, lookup_org: str) -> str | None:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            state = await setting_service.get_setting(PluginsState)
        for plugin_info in list(state.license_keys.values()):
            if plugin_info["plugin_name"] == lookup_name and plugin_info["plugin_author"] == lookup_org:
                return plugin_info["license_key"]
        return None

    def add_template(self, name: str, text: str | None = None, applicable_to: str = "", *, path: str) -> None:
        self.template_manager.add_template(
            templates.Template(name, text, applicable_to, prefix=os.path.join(path, "templates"))
        )

    def get_plugin_data_dir(self, plugin_name: str) -> str:
        return self.settings.get_plugin_data_dir(plugin_name)

    # End of plugin API implementation

    async def process_plugin_task(self, message: PluginTaskMessage) -> None:
        event = message.event
        data = message.data
        for_worker = message.for_worker
        if for_worker and not self.settings.IS_WORKER or (not for_worker and self.settings.IS_WORKER):  # pragma: no cover
            return
        if event not in self._events:
            return
        event_data = self._events[event]
        if not isinstance(data, dict) or data.keys() != event_data["params"]:
            return
        coros = (handler(event, data) for handler in event_data["handlers"])
        await asyncio.gather(*coros, return_exceptions=False)
