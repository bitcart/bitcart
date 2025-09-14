import json
from collections.abc import Callable
from typing import Any, TypeVar

from dishka import AsyncContainer

from api import models
from api.schemas.base import Schema
from api.schemas.policies import Policy
from api.services.crud.repositories import SettingRepository

T = TypeVar("T", bound=Schema)


def process_schema(schema_class: type[Schema]) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func._process_schema = schema_class  # type: ignore
        return func

    return decorator


class SettingService:
    def __init__(self, setting_repository: SettingRepository, container: AsyncContainer) -> None:
        self.setting_repository = setting_repository
        self.container = container
        self._async_init_handlers: dict[type[Schema], Callable[..., Any]] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, "_process_schema"):
                schema_class = attr._process_schema
                self._async_init_handlers[schema_class] = attr

    async def _dispatch_async_init(self, data: Schema) -> None:
        schema_class = type(data)
        if schema_class in self._async_init_handlers:
            handler = self._async_init_handlers[schema_class]
            await handler(data)

    async def get_setting(self, scheme: type[T], name: str | None = None) -> T:
        name = name or scheme.__name__.lower()
        item = await self.setting_repository.get_one_or_none(name=name)
        data = scheme() if not item else scheme(**json.loads(item.value))
        await self._dispatch_async_init(data)
        return data

    async def set_setting(self, scheme: T, name: str | None = None, *, write: bool = True) -> T:
        name = name or scheme.__class__.__name__.lower()
        json_data = scheme.model_dump(exclude_unset=True)
        update_data: dict[str, Any] = {"name": name, "value": json_data}
        model = await self.setting_repository.get_one_or_none(name=name)
        if model:
            value = json.loads(model.value)
            for key in json_data:
                value[key] = json_data[key]
            update_data["value"] = json.dumps(value)
            if write:
                model.update(**update_data)
        else:
            update_data["value"] = json.dumps(json_data)
            if write:
                await self.setting_repository.add(models.Setting(**update_data))
        data = scheme.__class__(**json.loads(update_data["value"]))
        await self._dispatch_async_init(data)
        return data

    @process_schema(Policy)
    async def init_policy(self, data: Policy) -> None:
        from api.services.coins import CoinService
        from api.templates import TemplateManager

        coin_service = await self.container.get(CoinService)
        template_manager = await self.container.get(TemplateManager)

        for key in coin_service.cryptos:
            if data.explorer_urls.get(key) is None:
                data.explorer_urls[key] = await coin_service.get_default_explorer(key)

        for key in template_manager.templates_strings["global"]:
            if data.global_templates.get(key) is None:
                data.global_templates[key] = ""

        for key in coin_service.cryptos:
            crypto = coin_service.cryptos[key]
            if not crypto.is_eth_based or crypto.coin_name in ("TRX", "XMR"):
                continue
            if data.rpc_urls.get(key) is None:
                data.rpc_urls[key] = coin_service.get_default_rpc(key)
