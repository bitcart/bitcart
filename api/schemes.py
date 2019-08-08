# pylint: disable=no-name-in-module, no-self-argument
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import File, UploadFile
from pydantic import BaseModel, EmailStr, validator
from pytz import utc


def now():
    return datetime.utcnow().replace(tzinfo=utc)


class BaseUser(BaseModel):
    username: str
    email: Optional[EmailStr] = ""  # type: ignore

    @validator('email', pre=True, always=False)
    def validate_email(cls, val):
        if val == "":
            return None
        return val

    class Config:
        orm_mode = True


class CreateUser(BaseUser):
    password: str


class User(BaseUser):
    id: int


class CreateWallet(BaseModel):
    name: str
    xpub: str = ""
    balance: Decimal = Decimal(0)
    user_id: int

    class Config:
        orm_mode = True


class Wallet(CreateWallet):
    id: int


class CreateStore(BaseModel):
    name: str
    domain: str = ""
    template: str = ""
    email: Optional[EmailStr] = ""  # type: ignore
    email_host: str = ""
    email_port: int = 25
    email_user: str = ""
    email_password: str = ""
    wallet_id: int

    @validator('email', pre=True, always=False)
    def validate_email(cls, val):
        if val == "":
            return None
        return val

    class Config:
        orm_mode = True


class Store(CreateStore):
    id: int


class CreateProduct(BaseModel):
    status: str = "active"
    amount: Decimal
    quantity: Decimal
    title: str
    date: Optional[datetime]
    description: str = ""
    store_id: int

    @validator("date", pre=True, always=True)
    def set_date(cls, v):
        return v or now()

    class Config:
        orm_mode = True


class Product(CreateProduct):
    id: int


class CreateInvoice(BaseModel):
    amount: Decimal
    status: str = "active"
    date: Optional[datetime] = now()
    bitcoin_address: str = ""
    bitcoin_url: str = ""
    products: List[int]

    @validator("date", pre=True, always=True)
    def set_date(cls, v):
        return v or now()

    class Config:
        orm_mode = True


class Invoice(CreateInvoice):
    id: int
