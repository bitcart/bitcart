import json
from typing import Any, cast

import pyotp
from dishka import AsyncContainer
from fastapi import HTTPException, Request
from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestedCredentialData,
    AuthenticatorAttachment,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    UserVerificationRequirement,
)
from sqlalchemy import Row, distinct, func, select

from api import constants, models, utils
from api.db import AsyncSession
from api.redis import Redis
from api.schemas.auth import LoginFIDOData, ResetPasswordFinalize
from api.schemas.policies import Policy
from api.schemas.tasks import SendVerificationEmailMessage
from api.schemas.tokens import CreateDBToken
from api.schemas.users import DisplayUser, DisplayUserWithToken
from api.services.auth import AuthService
from api.services.crud import CRUDService, ModelDictT
from api.services.crud.repositories import UserRepository
from api.services.crud.templates import TemplateService
from api.services.crud.tokens import TokenService
from api.services.plugin_registry import PluginRegistry
from api.services.settings import SettingService
from api.settings import Settings
from api.types import PasswordHasherProtocol, TasksBroker

RESET_REDIS_KEY = "reset_password"
VERIFY_REDIS_KEY = "verify_email"


class UserService(CRUDService[models.User]):
    repository_type = UserRepository

    def __init__(
        self,
        session: AsyncSession,
        container: AsyncContainer,
        redis_pool: Redis,
        broker: TasksBroker,
        settings: Settings,
        setting_service: SettingService,
        token_service: TokenService,
        auth_service: AuthService,
        password_hasher: PasswordHasherProtocol,
        template_service: TemplateService,
        plugin_registry: PluginRegistry,
    ) -> None:
        super().__init__(session, container)
        self.redis_pool = redis_pool
        self.broker = broker
        self.settings = settings
        self.setting_service = setting_service
        self.token_service = token_service
        self.auth_service = auth_service
        self.password_hasher = password_hasher
        self.template_service = template_service
        self.plugin_registry = plugin_registry

    async def prepare_create(self, data: dict[str, Any], user: models.User | None = None) -> dict[str, Any]:
        data = await super().prepare_create(data)
        data["totp_key"] = pyotp.random_base32()
        return data

    async def prepare_data(self, data: dict[str, Any]) -> dict[str, Any]:
        data = await super().prepare_data(data)
        if "password" in data:
            data["hashed_password"] = self.password_hasher.get_password_hash(data["password"])
            del data["password"]
        return data

    async def create(
        self, data: "ModelDictT[models.User]", auth_user: models.User | None = None, *, call_hooks: bool = True
    ) -> models.User:
        data = self._check_data(data, update=False)
        captcha_code = data.pop("captcha_code", None)
        register_off = (await self.setting_service.get_setting(Policy)).disable_registration
        if register_off and (not auth_user or not auth_user.is_superuser):
            raise HTTPException(422, "Registration disabled")
        if not auth_user or not auth_user.is_superuser:
            await self.auth_service.captcha_flow(captcha_code)
        is_superuser = False
        if auth_user is None:
            count = await self.repository.count()
            is_superuser = count == 0
        elif auth_user and auth_user.is_superuser:
            is_superuser = data["is_superuser"]
        data["is_superuser"] = is_superuser
        user = await super().create(data, auth_user, call_hooks=call_hooks)
        if is_superuser and auth_user is None:
            await self.plugin_registry.run_hook("first_user", user)
            await self.setting_service.set_setting(Policy(disable_registration=True))
        return user

    async def create_with_token(
        self, data: "ModelDictT[models.User]", auth_user: models.User | None = None
    ) -> DisplayUserWithToken:
        user = await self.create(data, auth_user)
        await self.session.commit()
        await self.broker.publish("send_verification_email", SendVerificationEmailMessage(user_id=user.id))
        policies = await self.setting_service.get_setting(Policy)
        data = DisplayUser.model_validate(user).model_dump()
        token = None
        if not policies.require_verified_email:
            token = await self.token_service.create(CreateDBToken(permissions=["full_control"], user_id=user.id))
            data["token"] = token.id
        await self.plugin_registry.run_hook("user_created", user, token)
        return DisplayUserWithToken.model_validate(data)

    async def get_stats(self, user: models.User) -> dict[str, int]:
        queries = []
        output_formats = []
        for index, label in enumerate(constants.CRUD_MODELS):
            model_key = label.rstrip("s ").capitalize()
            orm_model = getattr(models, model_key)
            query = select(func.count(distinct(orm_model.id)))
            if orm_model != models.User:
                query = query.where(orm_model.user_id == user.id)
            queries.append(query.label(label))
            output_formats.append((label, index))
        result = cast(Row[Any], (await self.session.execute(select(*queries))).first())
        response = {key: result[ind] for key, ind in output_formats}
        response.pop("users", None)
        return response

    def prepare_next_url(self, path: str) -> str:
        base = self.settings.admin_url.rstrip("/")
        tail = path.lstrip("/")
        return f"{base}/{tail}"

    async def generic_email_code_flow(
        self,
        redis_key: str,
        template_name: str,
        email_title: str,
        hook_name: str,
        user: models.User,
        next_url: str,
        expire_time: int = constants.SHORT_EXPIRATION,
    ) -> None:
        policy = await self.setting_service.get_setting(Policy)
        email_obj = utils.Email.get_email(policy)
        if not email_obj.is_enabled():  # pragma: no cover
            return
        code = utils.common.unique_verify_code()
        await self.redis_pool.set(f"{redis_key}:{code}", user.id, ex=expire_time)
        reset_url = utils.routing.get_redirect_url(next_url, code=code)
        template = await self.template_service.get_global_template(template_name)
        text = template.render(email=user.email, link=reset_url, code=code)
        email_obj.send_mail(user.email, text, email_title, use_html_templates=policy.use_html_templates)
        await self.plugin_registry.run_hook(f"{hook_name}_requested", user, code)

    async def reset_user_password(self, user: models.User) -> None:
        await self.generic_email_code_flow(
            RESET_REDIS_KEY,
            "forgotpassword",
            "Password reset",
            "password_reset",
            user,
            self.prepare_next_url("/forgotpassword"),
        )

    async def send_verification_email(self, user: models.User, expire_time: int = constants.VERIFY_EMAIL_EXPIRATION) -> None:
        await self.generic_email_code_flow(
            VERIFY_REDIS_KEY,
            "verifyemail",
            "Verify email",
            "verify_email",
            user,
            self.prepare_next_url("/login/email"),
            expire_time=expire_time,
        )

    async def change_password(self, user: models.User, password: str, logout_all: bool = True) -> None:
        await self.update({"password": password}, user.id)
        if logout_all:
            await self.token_service.logout_all(user)
        await self.plugin_registry.run_hook("password_changed", user)

    async def finalize_password_reset(self, code: str, data: ResetPasswordFinalize) -> bool:
        user_id = await self.redis_pool.getdel(f"{RESET_REDIS_KEY}:{code}")
        if user_id is None:
            raise HTTPException(422, "Invalid code")
        user = await self.get_or_none(user_id)
        if not user:  # pragma: no cover
            raise HTTPException(422, "Invalid code")
        await self.change_password(user, data.password, data.logout_all)
        return True

    async def finalize_email_verification(self, code: str, add_token: bool = False) -> dict[str, Any]:
        user_id = await self.redis_pool.getdel(f"{VERIFY_REDIS_KEY}:{code}")
        if user_id is None:
            raise HTTPException(422, "Invalid code")
        user = await self.get_or_none(user_id)
        if not user:  # pragma: no cover
            raise HTTPException(422, "Invalid code")
        user.is_verified = True
        response: dict[str, Any] = {"success": True, "token": None}
        if add_token:  # pragma: no cover
            token = await self.token_service.create(CreateDBToken(permissions=["full_control"], user_id=user.id))
            response["token"] = token.id
        return response

    async def verify_totp(self, user: models.User, code: str) -> list[str]:
        if not pyotp.TOTP(user.totp_key).verify(code.replace(" ", "")):
            raise HTTPException(422, "Invalid code")
        recovery_codes = [utils.authorization.generate_tfa_recovery_code() for _ in range(10)]
        user.update(tfa_enabled=True, recovery_codes=recovery_codes)
        return recovery_codes

    async def disable_totp(self, user: models.User) -> bool:
        user.update(tfa_enabled=False, totp_key=pyotp.random_base32())
        return True

    async def register_fido2_begin(self, user: models.User, auth_data: LoginFIDOData) -> dict[str, Any]:  # pragma: no cover
        existing_credentials = [AttestedCredentialData(bytes.fromhex(x["device_data"])) for x in user.fido2_devices]
        options, state = Fido2Server(PublicKeyCredentialRpEntity(name="Bitcart", id=auth_data.auth_host)).register_begin(
            PublicKeyCredentialUserEntity(
                id=user.id.encode(),
                name=user.email,
                display_name=user.email,
            ),
            existing_credentials,
            user_verification=UserVerificationRequirement.PREFERRED,
            authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM,
        )
        await self.redis_pool.set(
            f"{constants.FIDO2_REGISTER_KEY}:{user.id}", json.dumps(state), ex=constants.SHORT_EXPIRATION
        )
        return dict(options)

    async def fido2_complete_registration(self, user: models.User, request: Request) -> bool:  # pragma: no cover
        data = await request.json()
        if "name" not in data or "auth_host" not in data:
            raise HTTPException(422, "Missing name")
        auth_host = data["auth_host"]
        state = await self.redis_pool.get(f"{constants.FIDO2_REGISTER_KEY}:{user.id}")
        state = json.loads(state) if state else None
        try:
            auth_data = Fido2Server(PublicKeyCredentialRpEntity(name="Bitcart", id=auth_host)).register_complete(state, data)
        except Exception as e:
            raise HTTPException(422, str(e)) from None
        await self.redis_pool.delete(f"{constants.FIDO2_REGISTER_KEY}:{user.id}")
        user.fido2_devices.append(
            {
                "name": data["name"],
                "id": utils.common.unique_id(),
                "device_data": cast(AttestedCredentialData, auth_data.credential_data).hex(),
            }
        )
        return True

    async def fido2_delete_device(self, user: models.User, device_id: str) -> bool:  # pragma: no cover
        for device in user.fido2_devices:
            if device["id"] == device_id:
                user.fido2_devices.remove(device)
                break
        return True
