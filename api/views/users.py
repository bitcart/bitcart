import json

import pyotp
from fastapi import APIRouter, HTTPException, Request, Security
from fastapi.security import SecurityScopes
from fido2.server import Fido2Server
from fido2.webauthn import AttestedCredentialData, PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity
from sqlalchemy import distinct, func, select

from api import crud, db, models, schemes, settings, utils
from api.constants import FIDO2_REGISTER_KEY, SHORT_EXPIRATION
from api.plugins import run_hook

router = APIRouter()


@router.get("/stats")
async def get_stats(user: models.User = Security(utils.authorization.AuthDependency(), scopes=["full_control"])):
    queries = []
    output_formats = []
    for index, orm_model in enumerate(utils.routing.ModelView.crud_models):
        label = orm_model.__name__.lower() + "s"  # based on naming convention, i.e. User->users
        query = select([func.count(distinct(orm_model.id))])
        if orm_model != models.User:
            query = query.where(orm_model.user_id == user.id)
        queries.append(query.label(label))
        output_formats.append((label, index))
    result = await db.db.first(select(queries))
    response = {key: result[ind] for key, ind in output_formats}
    response.pop("users", None)
    return response


@router.get("/me", response_model=schemes.DisplayUser)
async def get_me(user: models.User = Security(utils.authorization.AuthDependency())):
    return user


@router.post("/me/settings", response_model=schemes.User)
async def set_settings(
    settings: schemes.UserPreferences,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["full_control"]),
):
    await user.set_json_key("settings", settings)
    return user


# NOTE: it is a good practice not to return any information whether the user exists in the system
@router.post("/reset_password")
async def reset_password(data: schemes.ResetPasswordData):
    await utils.authorization.captcha_flow(data.captcha_code)
    user = await utils.database.get_object(
        models.User, custom_query=models.User.query.where(models.User.email == data.email), raise_exception=False
    )
    if not user:
        return True
    await crud.users.reset_user_password(user, data.next_url)
    return True


@router.post("/reset_password/finalize/{code}")
async def finalize_password_reset(code: str, data: schemes.ResetPasswordFinalize):
    async with utils.redis.wait_for_redis():
        user_id = await settings.settings.redis_pool.execute_command("GETDEL", f"{crud.users.RESET_REDIS_KEY}:{code}")
    if user_id is None:
        raise HTTPException(422, "Invalid code")
    user = await utils.database.get_object(models.User, user_id, raise_exception=False)
    if not user:  # pragma: no cover
        raise HTTPException(422, "Invalid code")
    await crud.users.change_password(user, data.password, data.logout_all)
    return True


@router.post("/verify")
async def send_verification_email(data: schemes.VerifyEmailData):
    await utils.authorization.captcha_flow(data.captcha_code)
    user = await utils.database.get_object(
        models.User, custom_query=models.User.query.where(models.User.email == data.email), raise_exception=False
    )
    if not user:
        return True
    if user.is_verified:
        raise HTTPException(422, "User is already verified")
    await crud.users.send_verification_email(user, data.next_url)
    return True


@router.post("/verify/finalize/{code}")
async def finalize_email_verification(code: str):
    async with utils.redis.wait_for_redis():
        user_id = await settings.settings.redis_pool.execute_command("GETDEL", f"{crud.users.VERIFY_REDIS_KEY}:{code}")
    if user_id is None:
        raise HTTPException(422, "Invalid code")
    user = await utils.database.get_object(models.User, user_id, raise_exception=False)
    if not user:  # pragma: no cover
        raise HTTPException(422, "Invalid code")
    await user.update(is_verified=True).apply()
    return True


class CreateUserWithToken(schemes.DisplayUser):
    token: str


async def create_user(model: schemes.CreateUser, request: Request):
    try:
        auth_user = await utils.authorization.AuthDependency()(request, SecurityScopes([]))
    except HTTPException:
        auth_user = None
    user = await crud.users.create_user(model, auth_user)
    token = await utils.database.create_object(
        models.Token, schemes.CreateDBToken(permissions=["full_control"], user_id=user.id)
    )
    data = schemes.DisplayUser.from_orm(user).dict()
    data["token"] = token.id
    await run_hook("user_created", user, token)
    return data


@router.post("/2fa/totp/verify")
async def verify_totp(
    token_data: schemes.VerifyTOTP,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
):
    if not pyotp.TOTP(user.totp_key).verify(token_data.code.replace(" ", "")):
        raise HTTPException(422, "Invalid code")
    recovery_codes = [utils.authorization.generate_tfa_recovery_code() for _ in range(10)]
    await user.update(tfa_enabled=True, recovery_codes=recovery_codes).apply()
    return recovery_codes


@router.post("/2fa/disable")
async def disable_totp(
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
):
    await user.update(tfa_enabled=False, totp_key=pyotp.random_base32()).apply()
    return True


@router.post("/2fa/fido2/register/begin")
async def register_fido2(
    auth_data: schemes.LoginFIDOData,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
):  # pragma: no cover
    existing_credentials = list(map(lambda x: AttestedCredentialData(bytes.fromhex(x["device_data"])), user.fido2_devices))
    options, state = Fido2Server(PublicKeyCredentialRpEntity(name="BitcartCC", id=auth_data.auth_host)).register_begin(
        PublicKeyCredentialUserEntity(
            id=user.id.encode(),
            name=user.email,
            display_name=user.email,
        ),
        existing_credentials,
        user_verification="preferred",
        authenticator_attachment="cross-platform",
    )
    async with utils.redis.wait_for_redis():
        await settings.settings.redis_pool.set(f"{FIDO2_REGISTER_KEY}:{user.id}", json.dumps(state), ex=SHORT_EXPIRATION)
    return dict(options)


@router.post("/2fa/fido2/register/complete")
async def fido2_complete_registration(
    request: Request,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
):  # pragma: no cover
    data = await request.json()
    if "name" not in data or "auth_host" not in data:
        raise HTTPException(422, "Missing name")
    auth_host = data["auth_host"]
    async with utils.redis.wait_for_redis():
        state = await settings.settings.redis_pool.get(f"{FIDO2_REGISTER_KEY}:{user.id}")
        state = json.loads(state) if state else None
    try:
        auth_data = Fido2Server(PublicKeyCredentialRpEntity(name="BitcartCC", id=auth_host)).register_complete(state, data)
    except Exception as e:
        raise HTTPException(422, str(e))
    async with utils.redis.wait_for_redis():
        await settings.settings.redis_pool.delete(f"{FIDO2_REGISTER_KEY}:{user.id}")
    user.fido2_devices.append(
        {"name": data["name"], "id": utils.common.unique_id(), "device_data": auth_data.credential_data.hex()}
    )
    await user.update(fido2_devices=user.fido2_devices).apply()
    return True


@router.delete("/2fa/fido2/{device_id}")
async def fido2_delete_device(
    device_id: str,
    user: models.User = Security(utils.authorization.AuthDependency(), scopes=["token_management"]),
):  # pragma: no cover
    for device in user.fido2_devices:
        if device["id"] == device_id:
            user.fido2_devices.remove(device)
            break
    await user.update(fido2_devices=user.fido2_devices).apply()
    return True


utils.routing.ModelView.register(
    router,
    "/",
    models.User,
    schemes.User,
    schemes.CreateUser,
    display_model=schemes.DisplayUser,
    custom_methods={"post": crud.users.create_user},
    post_auth=False,
    request_handlers={"post": create_user},
    response_models={"post": CreateUserWithToken},
    scopes={
        "get_all": ["server_management"],
        "get_count": ["server_management"],
        "get_one": ["server_management"],
        "post": [],
        "patch": ["server_management"],
        "delete": ["server_management"],
    },
)
