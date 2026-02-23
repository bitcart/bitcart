import hashlib
import secrets

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import HTTPException, Request
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from api import models
from api.constants import RESET_TOKEN_BYTES, TFA_RECOVERY_LENGTH, VERIFY_CODE_LENGTH, AuthScopes
from api.types import AuthServiceProtocol
from api.utils.common import generate_hyphenated_code

CORE_SCOPES: dict[AuthScopes, str] = {
    AuthScopes.SERVER_MANAGEMENT: "Edit server settings",
    AuthScopes.TOKEN_MANAGEMENT: "Create, list or edit tokens",
    AuthScopes.WALLET_MANAGEMENT: "Create, list or edit wallets",
    AuthScopes.STORE_MANAGEMENT: "Create, list or edit stores",
    AuthScopes.DISCOUNT_MANAGEMENT: "Create, list or edit discounts",
    AuthScopes.PRODUCT_MANAGEMENT: "Create, list or edit products",
    AuthScopes.INVOICE_MANAGEMENT: "Create, list or edit invoices",
    AuthScopes.PAYOUT_MANAGEMENT: "Create, list or edit payouts",
    AuthScopes.NOTIFICATION_MANAGEMENT: "Create, list or edit notification providers",
    AuthScopes.TEMPLATE_MANAGEMENT: "Create, list or edit templates",
    AuthScopes.FILE_MANAGEMENT: "Create, list or edit files",
    AuthScopes.METRICS_MANAGEMENT: "Access to metrics",
    AuthScopes.FULL_CONTROL: "Full control over what current user has",
}
CORE_SCOPES_STR = {k.value: v for k, v in CORE_SCOPES.items()}
PLUGIN_SCOPES: dict[str, str] = {}


def get_all_scopes() -> dict[str, str]:
    return {**CORE_SCOPES_STR, **PLUGIN_SCOPES}


def register_scope(name: str, description: str) -> None:
    PLUGIN_SCOPES[name] = description


bearer_description = """Token authorization. Get a token by sending a POST request to `/token` endpoint (JSON-mode, preferred)
or `/token/oauth2` OAuth2-compatible endpoint.
Ensure to use only those permissions that your app actually needs. `full_control` gives access to all permissions of a user
To authorize, send an `Authorization` header with value of `Bearer <token>` (replace `<token>` with your token)
"""
optional_bearer_description = "Same as Bearer, but not required. Logic for unauthorized users depends on current endpoint"


type AuthResult = models.User | None | tuple[models.User, models.Token] | tuple[None, None]


def generate_verify_code() -> str:
    return generate_hyphenated_code(VERIFY_CODE_LENGTH // 2, upper=True)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(RESET_TOKEN_BYTES)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_tfa_recovery_code() -> str:
    return generate_hyphenated_code(TFA_RECOVERY_LENGTH)


class AuthDependency(OAuth2PasswordBearer):
    def __init__(
        self,
        enabled: bool = True,
        token_required: bool = True,
        token: str | None = None,
        return_token: bool = False,
    ) -> None:
        self.enabled = enabled
        self.return_token = return_token
        self.token = token
        super().__init__(
            tokenUrl="/token/oauth2",
            scopes=get_all_scopes(),
            auto_error=token_required,
            scheme_name="Bearer" if token_required else "BearerOptional",
            description=bearer_description if token_required else optional_bearer_description,
        )

    async def parse_token(self, request: Request) -> str | None:
        return self.token if self.token else await super().__call__(request)

    async def _process_request(
        self,
        request: Request,
        security_scopes: SecurityScopes,
        auth_service: FromDishka[AuthServiceProtocol],
    ) -> AuthResult:
        if not self.enabled:
            if self.return_token:  # pragma: no cover
                return None, None
            return None
        for auth_scope in security_scopes.scopes:
            scope_name = str(auth_scope)
            if scope_name not in get_all_scopes():
                raise ValueError(f"Invalid scope: {scope_name}")
        header_token: str | None = self.token if self.token else await super().__call__(request)
        user, token = await auth_service.find_user_and_check_permissions(header_token, security_scopes, request)
        if self.return_token:
            return user, token
        return user

    @inject
    async def __call__(  # type: ignore[override]
        self,
        request: Request,
        security_scopes: SecurityScopes,
        auth_service: FromDishka[AuthServiceProtocol],
    ) -> AuthResult:
        try:
            return await self._process_request(request, security_scopes, auth_service)
        except HTTPException:
            if self.auto_error:
                raise
            if self.return_token:
                return None, None
            return None


auth_dependency = AuthDependency()
optional_auth_dependency = AuthDependency(token_required=False)
