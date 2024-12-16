from decimal import Decimal

from fastapi import APIRouter, Body, HTTPException, Query, Security

from api import crud, models, schemes, utils
from api.ext.fxrate import calculate_rules
from api.views.stores.integrations import router as integrations_router

router = APIRouter()


@router.get("/{model_id}/ping")
async def ping_email(
    model_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["store_management"]),
):
    model = await utils.database.get_object(models.Store, model_id, user)
    return utils.StoreEmail.get_email(model).check_ping()


# NOTE: to_optional not required here because settings have default values set everywhere
@router.patch("/{model_id}/checkout_settings", response_model=schemes.DisplayStore)
async def set_store_checkout_settings(
    model_id: str,
    settings: schemes.StoreCheckoutSettings,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["store_management"]),
):
    model = await utils.database.get_object(models.Store, model_id, user)
    await model.set_json_key("checkout_settings", settings)
    return model


@router.patch("/{model_id}/email_settings", response_model=schemes.DisplayStore)
async def set_store_email_settings(
    model_id: str,
    settings: schemes.EmailSettings,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["store_management"]),
):
    model = await utils.database.get_object(models.Store, model_id, user)
    await model.set_json_key("email_settings", settings)
    return model


@router.patch("/{model_id}/rate_rules")
async def set_store_rate_rules(
    model_id: str,
    rules: str = Body(""),
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["store_management"]),
):
    model = await utils.database.get_object(models.Store, model_id, user)
    model.checkout_settings.rate_rules = rules
    try:
        result, resolved = await calculate_rules(rules, "BTC", "USD")
    except Exception as e:
        raise HTTPException(422, str(e)) from None
    await model.set_json_key("checkout_settings", model.checkout_settings)
    return f"BTC_USD: {result} resolved by {resolved}"


@router.get("/{model_id}/rates", response_model=schemes.RatesResponse)
async def get_store_rates(model_id: str, currencies: str = Query(...)):
    model = await utils.database.get_object(models.Store, model_id)
    results = []
    for currency in currencies.split(","):
        try:
            parts = currency.split("_")
            if len(parts) != 2:
                results.append({"rate": Decimal("NaN"), "message": f"{currency}: invalid currency pair"})
                continue
            result, resolved = await calculate_rules(model.checkout_settings.rate_rules, parts[0], parts[1])
            results.append({"rate": result, "message": f"{currency}: {result} (resolved by {resolved})"})
        except Exception as e:
            results.append({"rate": Decimal("NaN"), "message": f"{currency}: {str(e)}"})
    return {"rates": results}


@router.patch("/{model_id}/theme_settings", response_model=schemes.DisplayStore)
async def set_store_theme_settings(
    model_id: str,
    settings: schemes.StoreThemeSettings,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["store_management"]),
):
    model = await utils.database.get_object(models.Store, model_id, user)
    await model.set_json_key("theme_settings", settings)
    return model


@router.patch("/{model_id}/plugin_settings", response_model=schemes.DisplayStore)
async def set_store_plugin_settings(
    model_id: str,
    settings: schemes.StorePluginSettings,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["store_management"]),
):
    model = await utils.database.get_object(models.Store, model_id, user)
    await model.set_json_key("plugin_settings", settings)
    return model


crud_routes = utils.routing.ModelView.register(
    router,
    "/",
    models.Store,
    schemes.UpdateStore,
    schemes.CreateStore,
    schemes.DisplayStore,
    custom_methods={
        "post": crud.stores.create_store,
        "get_one": crud.stores.get_store,
    },
    get_one_model=None,
    get_one_auth=False,
    scopes=["store_management"],
)


router.include_router(integrations_router, prefix="/{store_id}/integrations")
