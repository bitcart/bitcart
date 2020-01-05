# pylint: disable=no-name-in-module, no-self-argument
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import File, UploadFile
from pydantic import BaseModel, EmailStr, validator

from .utils import now


class BaseUser(BaseModel):
    email: EmailStr
    is_superuser: Optional[bool] = False

    class Config:
        orm_mode = True


class CreateUser(BaseUser):
    password: str


class User(BaseUser):
    id: Optional[int]
    password: Optional[str]


class DisplayUser(BaseUser):
    id: Optional[int]


class CreateToken(BaseModel):
    email: str
    password: str


class TokenData(BaseModel):
    email: str


class RefreshToken(BaseModel):
    token: str


class CreateWallet(BaseModel):
    name: str
    xpub: str = ""
    currency: str = "btc"

    class Config:
        orm_mode = True


class Wallet(CreateWallet):
    id: Optional[int]
    user_id: int
    balance: Decimal = Decimal(0)


class CreateStore(BaseModel):
    name: str
    domain: str = ""
    template: str = ""
    email: Optional[EmailStr] = ""
    email_host: str = ""
    email_port: int = 25
    email_user: str = ""
    email_password: str = ""
    email_use_ssl: bool = True
    wallets: List[int]

    @validator("email", pre=True, always=False)
    def validate_email(cls, val):
        if val == "":
            return None
        return val

    class Config:
        orm_mode = True


class Store(CreateStore):
    id: Optional[int]


class CreateDiscount(BaseModel):
    name: str
    percent: int
    end_date: datetime
    description: str = ""
    promocode: str = ""
    currencies: str = ""

    class Config:
        orm_mode = True


class Discount(CreateDiscount):
    id: Optional[int]
    user_id: int


class CreateProduct(BaseModel):
    status: str = "active"
    amount: Decimal
    quantity: Decimal
    name: str
    date: Optional[datetime]
    download_url: Optional[str] = ""
    description: str = ""
    category: str = ""
    image: Optional[str] = ""
    store_id: int
    discounts: Optional[List[int]] = []

    @validator("date", pre=True, always=True)
    def set_date(cls, v):
        return v or now()

    @validator("status", pre=True, always=True)
    def set_status(cls, v):
        return v or "active"

    @validator("discounts", pre=True, always=True)
    def set_discounts(cls, v):
        return v or []

    class Config:
        orm_mode = True


class Product(CreateProduct):
    id: Optional[int]


class CreateInvoice(BaseModel):
    amount: Decimal
    buyer_email: Optional[EmailStr] = ""
    promocode: Optional[str] = ""
    discount: Optional[int]
    status: str = "Pending"
    date: Optional[datetime] = now()
    products: List[int]

    @validator("date", pre=True, always=True)
    def set_date(cls, v):
        return v or now()

    @validator("buyer_email", pre=True, always=False)
    def validate_buyer_email(cls, val):
        if val == "":
            return None
        return val

    @validator("discount", pre=True, always=True)
    def set_discount(cls, val):
        return val or None

    class Config:
        orm_mode = True


class Invoice(CreateInvoice):
    id: Optional[int]


class DisplayInvoice(Invoice):
    payments: dict = {}


class TxResponse(BaseModel):
    date: Optional[datetime]
    txid: str
    amount: str
