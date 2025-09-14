from typing import Any

from dishka import FromDishka
from fastapi import Body, Query, Security

from api import models, utils
from api.constants import AuthScopes
from api.schemas.misc import RatesResponse
from api.schemas.stores import (
    CreateStore,
    DisplayStore,
    PublicStore,
    StoreCheckoutSettings,
    StorePluginSettings,
    StoreThemeSettings,
    UpdateStore,
)
from api.services.crud.stores import StoreService
from api.utils.routing import create_crud_router

router = create_crud_router(
    CreateStore,
    UpdateStore,
    DisplayStore,
    StoreService,
    required_scopes=[AuthScopes.STORE_MANAGEMENT],
    disabled_endpoints={"get": True},
)


@router.get("/{model_id}", response_model=DisplayStore | PublicStore)
async def get_item(
    model_id: str,
    store_service: FromDishka[StoreService],
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[AuthScopes.STORE_MANAGEMENT]),
) -> Any:
    return await store_service.get_public_store(model_id, user)


@router.get("/{model_id}/ping")
async def ping_email(
    store_service: FromDishka[StoreService],
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.STORE_MANAGEMENT]),
) -> Any:
    model = await store_service.get(model_id, user)
    return utils.email.StoreEmail.get_email(model).check_ping()


# NOTE: to_optional not required here because settings have default values set everywhere
@router.patch("/{model_id}/checkout_settings", response_model=DisplayStore)
async def set_store_checkout_settings(
    store_service: FromDishka[StoreService],
    model_id: str,
    settings: StoreCheckoutSettings,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.STORE_MANAGEMENT]),
) -> Any:
    model = await store_service.get(model_id, user)
    await model.set_json_key("checkout_settings", settings)
    return model


@router.patch("/{model_id}/theme_settings", response_model=DisplayStore)
async def set_store_theme_settings(
    store_service: FromDishka[StoreService],
    model_id: str,
    settings: StoreThemeSettings,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.STORE_MANAGEMENT]),
) -> Any:
    model = await store_service.get(model_id, user)
    await model.set_json_key("theme_settings", settings)
    return model


@router.patch("/{model_id}/plugin_settings", response_model=DisplayStore)
async def set_store_plugin_settings(
    store_service: FromDishka[StoreService],
    model_id: str,
    settings: StorePluginSettings,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.STORE_MANAGEMENT]),
) -> Any:
    model = await store_service.get(model_id, user)
    await model.set_json_key("plugin_settings", settings)
    return model


@router.patch("/{model_id}/rate_rules")
async def set_store_rate_rules(
    store_service: FromDishka[StoreService],
    model_id: str,
    rules: str = Body(""),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.STORE_MANAGEMENT]),
) -> Any:
    return await store_service.set_store_rate_rules(model_id, rules, user)


@router.get("/{model_id}/rates", response_model=RatesResponse)
async def get_store_rates(store_service: FromDishka[StoreService], model_id: str, currencies: str = Query(...)) -> Any:
    return await store_service.get_store_rates(model_id, currencies.split(","))
