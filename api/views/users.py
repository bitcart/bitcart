from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, HTTPException, Query, Request, Security

from api import models, utils
from api.constants import AuthScopes
from api.schemas.auth import (
    ChangePassword,
    EmailVerifyResponse,
    LoginFIDOData,
    ResetPasswordData,
    ResetPasswordFinalize,
    VerifyEmailData,
    VerifyTOTP,
)
from api.schemas.users import CreateUser, DisplayUser, DisplayUserWithToken, UpdateUser, UserPreferences
from api.services.auth import AuthService
from api.services.crud.users import UserService
from api.types import PasswordHasherProtocol
from api.utils.routing import create_crud_router

router = APIRouter(route_class=DishkaRoute)


@router.get("/me", response_model=DisplayUser)
async def me(user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT])) -> Any:
    return user


@router.post("/me/settings", response_model=DisplayUser)
async def set_settings(
    settings: UserPreferences,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.FULL_CONTROL]),
) -> Any:
    await user.set_json_key("settings", settings)
    return user


# NOTE: it is a good practice not to return any information whether the user exists in the system
@router.post("/reset_password")
async def reset_password(
    auth_service: FromDishka[AuthService], user_service: FromDishka[UserService], data: ResetPasswordData
) -> Any:
    await auth_service.captcha_flow(data.captcha_code)
    user = await user_service.get_or_none(None, email=data.email)
    if not user:
        return True
    await user_service.reset_user_password(user)
    return True


@router.post("/reset_password/finalize/{code}")
async def finalize_password_reset(user_service: FromDishka[UserService], code: str, data: ResetPasswordFinalize) -> Any:
    return await user_service.finalize_password_reset(code, data)


@router.post("/verify")
async def send_verification_email(
    auth_service: FromDishka[AuthService],
    user_service: FromDishka[UserService],
    data: VerifyEmailData,
    auth_user: models.User | None = Security(
        utils.authorization.optional_auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]
    ),
) -> Any:
    if not auth_user:
        await auth_service.captcha_flow(data.captcha_code)
    user = await user_service.get_or_none(None, email=data.email)
    if not user:
        return True
    if user.is_verified:
        raise HTTPException(422, "User is already verified")
    await user_service.send_verification_email(user)
    return True


@router.post("/verify/finalize/{code}", response_model=EmailVerifyResponse)
async def finalize_email_verification(user_service: FromDishka[UserService], code: str, add_token: bool = Query(False)) -> Any:
    return await user_service.finalize_email_verification(code, add_token)


@router.post("/password")
async def change_password(
    password_hasher: FromDishka[PasswordHasherProtocol],
    user_service: FromDishka[UserService],
    data: ChangePassword,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:
    if not password_hasher.verify_password(data.old_password, user.hashed_password):
        raise HTTPException(422, "Invalid password")
    await user_service.change_password(user, data.password, data.logout_all)
    return True


@router.post("/2fa/totp/verify")
async def verify_totp(
    user_service: FromDishka[UserService],
    token_data: VerifyTOTP,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:
    return await user_service.verify_totp(user, token_data.code)


@router.post("/2fa/disable")
async def disable_totp(
    user_service: FromDishka[UserService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:
    return await user_service.disable_totp(user)


@router.post("/2fa/fido2/register/begin")
async def register_fido2(
    user_service: FromDishka[UserService],
    auth_data: LoginFIDOData,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:  # pragma: no cover
    return await user_service.register_fido2_begin(user, auth_data)


@router.post("/2fa/fido2/register/complete")
async def fido2_complete_registration(
    user_service: FromDishka[UserService],
    request: Request,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:  # pragma: no cover
    return await user_service.fido2_complete_registration(user, request)


@router.delete("/2fa/fido2/{device_id}")
async def fido2_delete_device(
    user_service: FromDishka[UserService],
    device_id: str,
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.TOKEN_MANAGEMENT]),
) -> Any:  # pragma: no cover
    return await user_service.fido2_delete_device(user, device_id)


@router.get("/stats")
async def get_stats(
    user_service: FromDishka[UserService],
    user: models.User = Security(utils.authorization.auth_dependency, scopes=[AuthScopes.FULL_CONTROL]),
) -> Any:
    return await user_service.get_stats(user)


create_crud_router(
    CreateUser,
    UpdateUser,
    DisplayUser,
    UserService,
    router=router,
    disabled_endpoints={"create": True},
    required_scopes=[AuthScopes.SERVER_MANAGEMENT],
)


@router.post("", response_model=DisplayUserWithToken)
async def create_user(
    data: CreateUser,
    service: FromDishka[UserService],
    auth_user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[]),
) -> Any:
    return await service.create_with_token(data, auth_user)
