from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union

from fastapi.exceptions import HTTPException
from pydantic import BaseModel, EmailStr, validator

from .constants import FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
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
    lightning_enabled: bool = False

    class Config:
        orm_mode = True

    @validator("lightning_enabled", pre=True, always=True)
    def set_lightning_enabled(cls, v):
        return v or False


class Wallet(CreateWallet):
    id: Optional[int]
    user_id: int
    balance: Decimal = Decimal(0)


class StoreCheckoutSettings(BaseModel):
    expiration: int = 15
    transaction_speed: int = 0
    underpaid_percentage: Decimal = 0
    custom_logo_link: str = ""
    recommended_fee_target_blocks: int = 1
    show_recommended_fee: bool = True
    use_dark_mode: bool = False
    use_html_templates: bool = False

    @validator("recommended_fee_target_blocks")
    def validate_recommended_fee_target_blocks(cls, v):
        if v not in FEE_ETA_TARGETS:
            message = ", ".join(map(str, FEE_ETA_TARGETS))
            raise HTTPException(422, f"Recommended fee confirmation target blocks must be either of: {message}")
        return v

    @validator("transaction_speed")
    def validate_transaction_speed(cls, v):
        if v < 0 or v > MAX_CONFIRMATION_WATCH:
            raise HTTPException(422, f"Transaction speed must be in range from 0 to {MAX_CONFIRMATION_WATCH}")
        return v

    @validator("underpaid_percentage")
    def validate_underpaid_percentage(cls, v):
        if v < 0 or v >= 100:
            raise HTTPException(422, "Underpaid percentage must be in range from 0 to 99.99")
        return float(v)


class BaseStore(CreatedMixin):
    name: str
    default_currency: str = "USD"
    email: Optional[EmailStr] = ""
    checkout_settings: Optional[StoreCheckoutSettings] = StoreCheckoutSettings()

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
    status: str = None
    products: Optional[Union[List[int], Dict[int, int]]] = {}

    @validator("status", pre=True, always=True)
    def set_status(cls, v):
        from .invoices import InvoiceStatus

        return v or InvoiceStatus.PENDING

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
    allow_anonymous_configurator: bool = True


class GlobalStorePolicy(BaseModel):
    pos_id: int = 1
    email_required: bool = True


class BatchSettings(BaseModel):
    ids: List[int]
    command: str


class OpenChannelScheme(BaseModel):
    node_id: str
    amount: Decimal


class CloseChannelScheme(BaseModel):
    channel_point: str
    force: bool = False


class LNPayScheme(BaseModel):
    invoice: str


class EventSystemMessage(BaseModel):
    event: str
    data: dict


class ConfiguratorDomainSettings(BaseModel):
    domain: Optional[str]
    https: Optional[bool] = True


class ConfiguratorCoinDescription(BaseModel):
    enabled: Optional[bool] = True
    network: Optional[str] = "mainnet"
    lightning: Optional[bool] = False


class ConfiguratorAdvancedSettings(BaseModel):
    installation_pack: Optional[str]
    bitcart_docker_repository: Optional[str]
    additional_components: Optional[List[str]]


class ConfiguratorSSHSettings(BaseModel):
    host: Optional[str]
    username: Optional[str]
    password: Optional[str]
    root_password: Optional[str]
    load_settings: Optional[bool] = True


class ConfiguratorDeploySettings(BaseModel):
    mode: str
    ssh_settings: Optional[ConfiguratorSSHSettings] = ConfiguratorSSHSettings()
    domain_settings: ConfiguratorDomainSettings
    coins: Dict[str, ConfiguratorCoinDescription]
    additional_services: Optional[List[str]]
    advanced_settings: ConfiguratorAdvancedSettings
