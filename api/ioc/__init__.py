from collections.abc import Iterable
from typing import Any, cast

from dishka import AsyncContainer, Provider, make_async_container

from api.ioc.app import provider as app_provider
from api.ioc.repositories import RepositoriesProvider
from api.ioc.services import ServicesProvider
from api.ioc.starlette import setup_dishka
from api.plugins import PluginObjects, build_plugin_di_context, init_plugins, load_plugins
from api.settings import Settings
from api.tasks import broker, client_tasks_broker
from api.types import ClientTasksBroker, TasksBroker


def get_providers() -> list[Provider]:
    return [app_provider, ServicesProvider(), RepositoriesProvider()]


def build_container(
    settings: Settings,
    *,
    extra_providers: Iterable[Provider] = (),
    context_overrides: dict[type[Any], Any] | None = None,
    include_plugins: bool = True,
    **kwargs: Any,
) -> AsyncContainer:
    context: dict[type[Any], Any] = {Settings: settings, TasksBroker: broker, ClientTasksBroker: client_tasks_broker}
    providers = get_providers()
    providers.extend(extra_providers)
    if include_plugins:
        plugin_classes, plugin_providers = load_plugins(settings)
        plugin_objects = init_plugins(plugin_classes)
        plugin_context = build_plugin_di_context(plugin_objects)
        context.update(
            {
                PluginObjects: plugin_objects,
                **cast(dict[type[Any], Any], plugin_context),
            }
        )
        providers.extend(plugin_providers)
    if context_overrides:
        context.update(context_overrides)
    return make_async_container(
        *providers,
        context=context,
        **kwargs,
    )


__all__ = ["get_providers", "setup_dishka", "build_container"]
