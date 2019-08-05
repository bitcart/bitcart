from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pytz import utc
from fastapi import File, UploadFile
from pydantic import BaseModel, EmailStr, validator


def now():
    return datetime.utcnow().replace(tzinfo=utc)


class User(BaseModel):
    username: str
    password: str
    email: Optional[EmailStr] = ""


class Wallet(BaseModel):
    name: str
    xpub: str = ""
    balance: Decimal = Decimal(0)
    user: User


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
