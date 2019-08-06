from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Union

from fastapi import File, UploadFile
from pydantic import BaseModel, EmailStr, validator
from pytz import utc


def now():
    return datetime.utcnow().replace(tzinfo=utc)


class User(BaseModel):
    id: Optional[int]
    username: str
    email: Optional[EmailStr] = ""

    @validator('email', pre=True, always=False)
    def validate_email(cls, val):
        if val == "":
            return None
        return val

    class Config:
        orm_mode = True


class CreateUser(User):
    password: str


class CreateWallet(BaseModel):
    name: str
    xpub: str = ""
    balance: Decimal = Decimal(0)
    user: Union[int, User]

    class Config:
        orm_mode = True


class Wallet(CreateWallet):
    id: Optional[int]


class Store(BaseModel):
    name: str
    domain: str = ""
    template: str = ""
    email: Optional[EmailStr] = ""
    email_host: str = ""
    email_port: int = 25
    email_user: str = ""
    email_password: str = ""
    wallet: Wallet


class Product(BaseModel):
    status: str = "active"
    amount: Decimal
    quantity: Decimal
    title: str
    date: datetime
    description: str = ""
    image: UploadFile = File(...)
    store: Store

    @validator("date", pre=True)
    def set_date(cls, v):
        return v or now()


class Invoice(BaseModel):
    amount: Decimal
    status: str = "active"
    date: datetime = now()
    bitcoin_address: str = ""
    bitcoin_url: str = ""
    products: List[Product]

    @validator("date", pre=True)
    def set_date(cls, v):
        return v or now()
