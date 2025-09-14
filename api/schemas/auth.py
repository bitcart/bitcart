from pydantic import EmailStr

from api.schemas.base import Schema
from api.schemas.tokens import CreateDBToken


# TODO: different schemas based on tfa_types
class AuthResponse(CreateDBToken):
    id: str | None = None
    access_token: str | None
    token_type: str
    tfa_required: bool
    tfa_code: str | None
    tfa_types: list[str]
    user_id: str = ""


class VerifyTOTP(Schema):
    code: str


class TOTPAuth(VerifyTOTP):
    token: str


class FIDO2Auth(Schema):
    token: str
    auth_host: str


class LoginFIDOData(Schema):
    auth_host: str


class RegisterFidoData(Schema):
    name: str


class ChangePassword(Schema):
    old_password: str
    password: str
    logout_all: bool = False


class ResetPasswordData(Schema):
    email: EmailStr
    captcha_code: str = ""


class VerifyEmailData(ResetPasswordData):
    pass


class ResetPasswordFinalize(Schema):
    password: str
    logout_all: bool = True


class EmailVerifyResponse(Schema):
    success: bool
    token: str | None
