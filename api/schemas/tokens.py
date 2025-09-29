from pydantic import EmailStr

from api.schemas.base import Schema, TimestampedSchema


class HTTPCreateToken(Schema):
    app_id: str = ""
    redirect_url: str = ""
    permissions: list[str] = []


class HTTPCreateLoginToken(HTTPCreateToken):
    email: EmailStr = ""
    password: str = ""
    captcha_code: str = ""
    strict: bool = True


class CreateDBToken(HTTPCreateToken):
    user_id: str


class EditToken(Schema):
    redirect_url: str = ""


class Token(CreateDBToken, TimestampedSchema):
    id: str
