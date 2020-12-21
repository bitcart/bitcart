from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, validator

from .utils import now


class CreatedMixin(BaseModel):
    created: Optional[datetime]

    @validator("created", pre=True, always=True)
    def set_created(cls, v):
        return v or now()


class BaseUser(CreatedMixin):
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


class HTTPCreateToken(CreatedMixin):
    app_id: str = ""
    redirect_url: str = ""
    permissions: List[str] = []

    @validator("permissions", pre=True, always=False)
    def validate_permissions(cls, val):
        if val == "":
            return []
        return val

    class Config:
        orm_mode = True


class HTTPCreateLoginToken(HTTPCreateToken):
    email: str = ""
    password: str = ""
    strict: bool = True


class EditToken(BaseModel):
    redirect_url: str = ""


class CreateDBToken(HTTPCreateToken):
    user_id: int


class Token(CreateDBToken):
    id: str


class CreateWallet(CreatedMixin):
    name: str
    xpub: str = ""
    currency: str = "btc"

    class Config:
        orm_mode = True


class Wallet(CreateWallet):
    id: Optional[int]
    user_id: int
    balance: Decimal = Decimal(0)


class BaseStore(CreatedMixin):
    name: str
    default_currency: str = "USD"
    email: Optional[EmailStr] = ""

    @validator("email", pre=True, always=False)
    def validate_email(cls, val):
        if val == "":
            return None
        return val

    class Config:
        orm_mode = True


class CreateStore(BaseStore):
    email_host: str = ""
    email_port: int = 25
    email_user: str = ""
    email_password: str = ""
    email_use_ssl: bool = True
    wallets: List[int]
    expiration: int = 15
    notifications: Optional[List[int]] = []
    templates: Optional[Dict[str, int]] = {}

    @validator("notifications", pre=True, always=True)
    def set_notifications(cls, v):
        return v or []

    @validator("templates", pre=True, always=True)
    def set_templates(cls, v):
        return v or {}


class PublicStore(BaseStore):
    id: Optional[int]
    user_id: int


class Store(CreateStore):
    id: Optional[int]
    user_id: int


class CreateDiscount(CreatedMixin):
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


class CreateNotification(CreatedMixin):
    name: str
    provider: str
    data: dict

    class Config:
        orm_mode = True


class Notification(CreateNotification):
    id: Optional[int]
    user_id: int


class CreateTemplate(CreatedMixin):
    name: str
    text: str

    class Config:
        orm_mode = True


class Template(CreateTemplate):
    id: Optional[int]
    user_id: int


class CreateProduct(CreatedMixin):
    status: str = "active"
    price: Decimal
    quantity: Decimal
    name: str
    download_url: Optional[str] = ""
    description: str = ""
    category: str = ""
    image: Optional[str] = ""
    store_id: int
    discounts: Optional[List[int]] = []
    templates: Optional[Dict[str, int]] = {}

    @validator("status", pre=True, always=True)
    def set_status(cls, v):
        return v or "active"

    @validator("discounts", pre=True, always=True)
    def set_discounts(cls, v):
        return v or []

    @validator("templates", pre=True, always=True)
    def set_templates(cls, v):
        return v or {}

    class Config:
        orm_mode = True


class Product(CreateProduct):
    id: Optional[int]
    store_id: Optional[int]
    user_id: int


class CreateInvoice(CreatedMixin):
    price: Decimal
    store_id: int
    currency: str = ""
    paid_currency: Optional[str] = ""
    order_id: Optional[str] = ""
    notification_url: Optional[str] = ""
    redirect_url: Optional[str] = ""
    buyer_email: Optional[EmailStr] = ""
    promocode: Optional[str] = ""
    discount: Optional[int]
    status: str = "Pending"
    products: Optional[Union[List[int], Dict[int, int]]] = {}

    @validator("buyer_email", pre=True, always=False)
    def validate_buyer_email(cls, val):
        if val == "":
            return None
        return val  # pragma: no cover

    @validator("discount", pre=True, always=True)
    def set_discount(cls, val):
        return val or None

    @validator("products", pre=True, always=True)
    def set_products(cls, v):
        return v or []

    class Config:
        orm_mode = True


class Invoice(CreateInvoice):
    id: Optional[int]
    store_id: Optional[int]
    user_id: int
    currency: str = "USD"


class DisplayInvoice(Invoice):
    time_left: int
    expiration: int
    expiration_seconds: int
    payments: list = []


class TxResponse(BaseModel):
    date: Optional[datetime]
    txid: str
    amount: str


class Policy(BaseModel):
    disable_registration: bool = False
    discourage_index: bool = False
    check_updates: bool = True


class GlobalStorePolicy(BaseModel):
    pos_id: int = 1


class BatchSettings(BaseModel):
    ids: List[int]
    command: str
