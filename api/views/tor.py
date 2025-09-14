from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Security

from api import models, utils
from api.constants import AuthScopes
from api.services.ext.tor import TorService
from api.services.plugin_registry import PluginRegistry

router = APIRouter(route_class=DishkaRoute)


@router.get("/services")
async def get_services(
    tor_service: FromDishka[TorService],
    plugin_registry: FromDishka[PluginRegistry],
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    key = "services_dict" if user else "anonymous_services_dict"
    return await plugin_registry.apply_filters("tor_services", await tor_service.get_data(key, {}, json_decode=True))
