from fastapi import APIRouter, HTTPException, Security

from api import crud, models, schemes, utils

router = APIRouter()


@router.get("/{model_id}/ping")  # TODO: check user (by utility)
async def ping_email(
    model_id: int,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["store_management"]),
):
    model = await models.Store.query.where(models.Store.id == model_id).gino.first()
    if not model:
        raise HTTPException(404, f"Store with id {model_id} does not exist!")
    return utils.email.check_ping(
        model.email_host,
        model.email_port,
        model.email_user,
        model.email_password,
        model.email,
        model.email_use_ssl,
    )


@router.patch("/{model_id}/checkout_settings", response_model=schemes.Store)  # TODO: check user
async def set_store_checkout_settings(
    model_id: int,
    settings: schemes.StoreCheckoutSettings,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["store_management"]),
):
    model = await models.Store.get(model_id)
    if not model:
        raise HTTPException(404, f"Store with id {model_id} does not exist!")
    await model.set_setting(settings)
    await crud.stores.store_add_related(model)
    return model


utils.routing.ModelView.register(
    router,
    "/",
    models.Store,
    schemes.Store,
    schemes.CreateStore,
    custom_methods={
        "get": crud.stores.get_stores,
        "get_one": crud.stores.get_store,
        "post": crud.stores.create_store,
        "delete": crud.stores.delete_store,
    },
    get_one_model=None,
    get_one_auth=False,
    scopes=["store_management"],
)
