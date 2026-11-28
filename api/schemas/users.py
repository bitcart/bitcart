from typing import Any

from pydantic import EmailStr

from api.schemas.base import MetadataInput, MetadataOutput, Schema, TimestampedSchema
from api.schemas.misc import InternalHosts


class UserPreferences(Schema):
    balance_currency: str = "USD"
    fetch_balance: bool = True


class BaseUser(MetadataInput):
    email: EmailStr
    is_superuser: bool = False
    settings: UserPreferences = UserPreferences()


class CreateUser(BaseUser):
    password: str
    captcha_code: str = ""


class UpdateUser(BaseUser):
    password: str
    is_verified: bool
    is_enabled: bool
    allowed_internal_hosts: InternalHosts = []


User = UpdateUser


class PublicUser(Schema):
    id: str
    email: EmailStr


class InfoUser(MetadataOutput, BaseUser):
    id: str
    is_verified: bool
    is_enabled: bool
    totp_key: str
    totp_url: str
    tfa_enabled: bool
    fido2_devices: list[dict[str, Any]]


class DisplayUser(InfoUser, TimestampedSchema):
    pass


class ManagedUser(DisplayUser):
    allowed_internal_hosts: list[str]


class DisplayUserWithToken(DisplayUser):
    token: str | None = None
