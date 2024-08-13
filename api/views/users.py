import json
from typing import Optional

import pyotp
from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, Security
from fastapi.responses import RedirectResponse
from fido2.server import Fido2Server
from fido2.webauthn import AttestedCredentialData, PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity
from sqlalchemy import distinct, func, select

from api import crud, db, events, models, schemes, settings, utils
from api.constants import FIDO2_REGISTER_KEY, SHORT_EXPIRATION
from api.plugins import run_hook
from api.social import available_providers

router = APIRouter()


@router.get("/stats")
async def get_stats(user: models.User = Security(utils.authorization.auth_dependency, scopes=["full_control"])):
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
async def get_me(user: models.User = Security(utils.authorization.auth_dependency)):
    return user


@router.post("/me/settings", response_model=schemes.DisplayUser)
async def set_settings(
    settings: schemes.UserPreferences,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["full_control"]),
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
    await crud.users.reset_user_password(user)
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
async def send_verification_email(
    data: schemes.VerifyEmailData,
    auth_user: Optional[models.User] = Security(utils.authorization.optional_auth_dependency, scopes=["token_management"]),
):
    if not auth_user:
        await utils.authorization.captcha_flow(data.captcha_code)
    user = await utils.database.get_object(
        models.User, custom_query=models.User.query.where(models.User.email == data.email), raise_exception=False
    )
    if not user:
        return True
    if user.is_verified:
        raise HTTPException(422, "User is already verified")
    await crud.users.send_verification_email(user)
    return True


@router.post("/verify/finalize/{code}", response_model=schemes.EmailVerifyResponse)
async def finalize_email_verification(code: str, add_token: bool = Query(False)):
    async with utils.redis.wait_for_redis():
        user_id = await settings.settings.redis_pool.execute_command("GETDEL", f"{crud.users.VERIFY_REDIS_KEY}:{code}")
    if user_id is None:
        raise HTTPException(422, "Invalid code")
    user = await utils.database.get_object(models.User, user_id, raise_exception=False)
    if not user:  # pragma: no cover
        raise HTTPException(422, "Invalid code")
    await user.update(is_verified=True).apply()
    response = {"success": True, "token": None}
    if add_token:  # pragma: no cover
        token = await utils.database.create_object(
            models.Token, schemes.CreateDBToken(permissions=["full_control"], user_id=user.id)
        )
        response["token"] = token.id
    return response


async def create_user(
    model: schemes.CreateUser,
    auth_user: Optional[models.User] = Security(utils.authorization.optional_auth_dependency, scopes=[]),
):
    user = await crud.users.create_user(model, auth_user)
    await events.event_handler.publish("send_verification_email", {"id": user.id})
    policies = await utils.policies.get_setting(schemes.Policy)
    data = schemes.DisplayUser.model_validate(user).model_dump()
    token = None
    if not policies.require_verified_email:
        token = await utils.database.create_object(
            models.Token, schemes.CreateDBToken(permissions=["full_control"], user_id=user.id)
        )
        data["token"] = token.id
    await run_hook("user_created", user, token)
    return data


@router.post("/password")
async def change_password(
    data: schemes.ChangePassword,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["token_management"]),
):
    if not utils.authorization.verify_password(data.old_password, user.hashed_password):
        raise HTTPException(422, "Invalid password")
    await crud.users.change_password(user, data.password, data.logout_all)
    return True


@router.post("/2fa/totp/verify")
async def verify_totp(
    token_data: schemes.VerifyTOTP,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["token_management"]),
):
    if not pyotp.TOTP(user.totp_key).verify(token_data.code.replace(" ", "")):
        raise HTTPException(422, "Invalid code")
    recovery_codes = [utils.authorization.generate_tfa_recovery_code() for _ in range(10)]
    await user.update(tfa_enabled=True, recovery_codes=recovery_codes).apply()
    return recovery_codes


@router.post("/2fa/disable")
async def disable_totp(
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["token_management"]),
):
    await user.update(tfa_enabled=False, totp_key=pyotp.random_base32()).apply()
    return True


@router.post("/2fa/fido2/register/begin")
async def register_fido2(
    auth_data: schemes.LoginFIDOData,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["token_management"]),
):  # pragma: no cover
    existing_credentials = list(map(lambda x: AttestedCredentialData(bytes.fromhex(x["device_data"])), user.fido2_devices))
    options, state = Fido2Server(PublicKeyCredentialRpEntity(name="Bitcart", id=auth_data.auth_host)).register_begin(
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
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["token_management"]),
):  # pragma: no cover
    data = await request.json()
    if "name" not in data or "auth_host" not in data:
        raise HTTPException(422, "Missing name")
    auth_host = data["auth_host"]
    async with utils.redis.wait_for_redis():
        state = await settings.settings.redis_pool.get(f"{FIDO2_REGISTER_KEY}:{user.id}")
        state = json.loads(state) if state else None
    try:
        auth_data = Fido2Server(PublicKeyCredentialRpEntity(name="Bitcart", id=auth_host)).register_complete(state, data)
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
    user: models.User = Security(utils.authorization.auth_dependency, scopes=["token_management"]),
):  # pragma: no cover
    for device in user.fido2_devices:
        if device["id"] == device_id:
            user.fido2_devices.remove(device)
            break
    await user.update(fido2_devices=user.fido2_devices).apply()
    return True


@router.get("/login/{sso_provider}")
async def sso_login(request: Request, sso_provider: str = Path()):
    if sso_provider not in available_providers:
        raise HTTPException(404, "Invalid provider")
    redirect_uri = request.url_for("auth", sso_provider=sso_provider)
    oauth_client = getattr(settings.settings.oauth, sso_provider)
    return await oauth_client.authorize_redirect(request, redirect_uri)


@router.get("/auth/{sso_provider}")
async def auth(request: Request, response: Response, sso_provider: str = Path()):
    response = RedirectResponse(
        "http://" + settings.settings.admin_host + "/",
    )
    # skip unknown provider
    if sso_provider not in settings.settings.oauth_providers:
        raise HTTPException(404, "Invalid provider")
    # get access_token
    try:
        oauth_client = getattr(settings.settings.oauth, sso_provider)
        token = await oauth_client.authorize_access_token(request)
    except Exception:
        raise HTTPException(status_code=400, detail="Fail to get access token")

    # get data by token
    user = await oauth_client.userinfo(token=token)
    if not user:
        raise HTTPException(status_code=400, detail="Missing user data")
    data = settings.settings.oauth_providers.get(sso_provider).process_data(user, token)
    if not data["email"]:
        raise HTTPException(status_code=400, detail="Missing user data")

    # if user not exist create new
    existing_user = await models.User.query.where(models.User.email == data["email"]).gino.first()
    token = None
    if not existing_user:
        try:
            data["is_verified"] = True
            existing_user = await create_user(
                schemes.CreateUser(**data, password=utils.common.get_unusable_hash()), existing_user
            )
            token = "Bearer " + existing_user["token"]
        except Exception:  # pragma: no cover
            raise HTTPException(status_code=400, detail="Missing user data")
    elif existing_user and sso_provider == existing_user.sso_type:
        policies = await utils.policies.get_setting(schemes.Policy)
        if not policies.require_verified_email:
            token = (
                "Bearer "
                + (
                    await utils.database.create_object(
                        models.Token, schemes.CreateDBToken(permissions=["full_control"], user_id=existing_user.id)
                    )
                ).id
            )
    else:
        response = RedirectResponse(
            "http://" + settings.settings.admin_host + "?error=User already exists",
        )
        return response

    response.set_cookie("auth._token.local", token)
    return response


crud_routes = utils.routing.ModelView.register(
    router,
    "/",
    models.User,
    schemes.User,
    schemes.CreateUser,
    schemes.DisplayUser,
    custom_methods={"post": crud.users.create_user},
    post_auth=False,
    request_handlers={"post": create_user},
    response_models={"post": schemes.DisplayUserWithToken},
    scopes={
        "get_all": ["server_management"],
        "get_count": ["server_management"],
        "get_one": ["server_management"],
        "post": [],
        "patch": ["server_management"],
        "delete": ["server_management"],
    },
)
