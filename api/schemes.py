from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union

import paramiko
from fastapi.exceptions import HTTPException
from pydantic import BaseModel as PydanticBaseModel
from pydantic import EmailStr, root_validator, validator
from pydantic.utils import GetterDict as PydanticGetterDict

from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS, FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
from api.ext.moneyformat import currency_table
from api.types import Money


class GetterDict(PydanticGetterDict):  # for some reason, by default adding keys is not allowed
    def __setitem__(self, key, value):
        return setattr(self._obj, key, value)


class BaseModel(PydanticBaseModel):
    class Config:
        getter_dict = GetterDict


class CreatedMixin(BaseModel):
    created: Optional[datetime]

    @validator("created", pre=True, always=True)
    def set_created(cls, v):
        from api.utils.time import now

        return v or now()


class UserPreferences(BaseModel):
    balance_currency: str = "USD"


class BaseUser(CreatedMixin):
    email: EmailStr
    is_superuser: Optional[bool] = False
    settings: UserPreferences = UserPreferences()

    class Config:
        orm_mode = True


class CreateUser(BaseUser):
    password: str


class User(BaseUser):
    id: Optional[str]
    password: Optional[str]


class DisplayUser(BaseUser):
    id: Optional[str]


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
    user_id: str


class Token(CreateDBToken):
    id: str


class CreateWallet(CreatedMixin):
    name: str
    xpub: str = ""
    currency: str = "btc"
    lightning_enabled: bool = False
    label: str = ""
    hint: str = ""
    contract: str = ""

    class Config:
        orm_mode = True

    @validator("contract", pre=True, always=False)
    def validate_contract(cls, val):
        return val or ""

    @validator("lightning_enabled", pre=True, always=True)
    def set_lightning_enabled(cls, v):
        return v or False

    @validator("label", pre=True)
    def set_label(cls, val):
        return val or ""

    @validator("hint", pre=True)
    def set_hint(cls, val):
        return val or ""


class Wallet(CreateWallet):
    id: Optional[str]
    user_id: str
    error: bool = False
    balance: Money

    @root_validator(pre=True)
    def set_balance(cls, values):
        if "balance" in values:
            values["balance"] = currency_table.format_decimal(
                values.get("currency"), values["balance"], divisibility=values.get("divisibility")
            )
        return values


class StoreCheckoutSettings(BaseModel):
    expiration: int = 15
    transaction_speed: int = 0
    underpaid_percentage: Decimal = 0
    custom_logo_link: str = ""
    recommended_fee_target_blocks: int = 1
    show_recommended_fee: bool = True
    use_dark_mode: bool = False
    use_html_templates: bool = False
    email_required: bool = True
    ask_address: bool = False

    @validator("recommended_fee_target_blocks")
    def validate_recommended_fee_target_blocks(cls, v):
        from api import utils

        return utils.common.validate_list(v, FEE_ETA_TARGETS, "Recommended fee confirmation target blocks")

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


class StoreThemeSettings(BaseModel):
    store_theme_url: str = ""
    admin_theme_url: str = ""


class StoreShopifySettings(BaseModel):
    shop_name: str = ""
    api_key: str = ""
    api_secret: str = ""


class StorePluginSettings(BaseModel):
    shopify: StoreShopifySettings = StoreShopifySettings()


class BaseStore(CreatedMixin):
    name: str
    default_currency: str = "USD"
    email: Optional[EmailStr] = ""
    checkout_settings: StoreCheckoutSettings = StoreCheckoutSettings()
    theme_settings: StoreThemeSettings = StoreThemeSettings()

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
    wallets: List[str]
    notifications: Optional[List[str]] = []
    templates: Optional[Dict[str, str]] = {}
    plugin_settings: StorePluginSettings = StorePluginSettings()

    @validator("notifications", pre=True, always=True)
    def set_notifications(cls, v):
        return v or []

    @validator("templates", pre=True, always=True)
    def set_templates(cls, v):
        return v or {}


class PublicStore(BaseStore):
    id: Optional[str]
    user_id: str
    currency_data: dict


class Store(CreateStore):
    id: Optional[str]
    user_id: str
    currency_data: dict


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
    id: Optional[str]
    user_id: str


class CreateNotification(CreatedMixin):
    name: str
    provider: str
    data: dict

    class Config:
        orm_mode = True

    @validator("provider")
    def validate_provider(cls, v):
        from api import settings

        if v not in settings.settings.notifiers:
            raise HTTPException(422, "Unsupported notificaton provider")
        return v


class Notification(CreateNotification):
    id: Optional[str]
    user_id: str


class CreateTemplate(CreatedMixin):
    name: str
    text: str

    class Config:
        orm_mode = True


class Template(CreateTemplate):
    id: Optional[str]
    user_id: str


class CreateProduct(CreatedMixin):
    status: str = "active"
    price: Decimal
    quantity: Decimal
    name: str
    download_url: Optional[str] = ""
    description: str = ""
    category: str = ""
    image: Optional[str] = ""
    store_id: str
    discounts: Optional[List[str]] = []
    templates: Optional[Dict[str, str]] = {}

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
    id: Optional[str]
    store_id: Optional[str]
    user_id: str
    price: Money

    @root_validator(pre=True)
    def set_price(cls, values):
        if "price" in values:
            values["price"] = currency_table.format_decimal(values.get("currency"), values["price"])
        return values


class CreateInvoice(CreatedMixin):
    price: Decimal
    store_id: str
    currency: str = ""
    paid_currency: Optional[str] = ""
    order_id: Optional[str] = ""
    notification_url: Optional[str] = ""
    redirect_url: Optional[str] = ""
    buyer_email: Optional[EmailStr] = ""
    promocode: Optional[str] = ""
    shipping_address: Optional[str] = ""
    notes: Optional[str] = ""
    discount: Optional[str]
    status: str = None
    products: Optional[Union[List[str], Dict[str, int]]] = {}

    @validator("status", pre=True, always=True)
    def set_status(cls, v):
        from api.invoices import InvoiceStatus

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


class CustomerUpdateData(BaseModel):
    buyer_email: Optional[EmailStr] = ""
    shipping_address: Optional[str] = ""
    notes: Optional[str] = ""

    @validator("buyer_email", pre=True, always=False)
    def validate_buyer_email(cls, val):
        if val == "":
            return None
        return val  # pragma: no cover


class Invoice(CreateInvoice):
    id: Optional[str]
    store_id: Optional[str]
    user_id: str
    currency: str = "USD"
    price: Money

    @root_validator(pre=True)
    def set_price(cls, values):
        if "price" in values:
            values["price"] = currency_table.format_decimal(values.get("currency"), values["price"])
        return values


class DisplayInvoice(Invoice):
    time_left: int
    expiration: int
    expiration_seconds: int
    payments: list = []


class TxResponse(BaseModel):
    date: Optional[datetime]
    txid: str
    amount: str


class BalanceResponse(BaseModel):
    confirmed: Money
    unconfirmed: Money
    unmatured: Money
    lightning: Money


class Policy(BaseModel):
    disable_registration: bool = False
    discourage_index: bool = False
    check_updates: bool = True
    allow_anonymous_configurator: bool = True


class GlobalStorePolicy(BaseModel):
    pos_id: str = ""


class BackupsPolicy(BaseModel):
    provider: str = "local"
    scheduled: bool = False
    frequency: str = "weekly"
    environment_variables: Dict[str, str] = {}

    @validator("provider")
    def validate_provider(cls, v):
        from api import utils

        return utils.common.validate_list(v, BACKUP_PROVIDERS, "Backup provider")

    @validator("frequency")
    def validate_frequency(cls, v):
        from api import utils

        return utils.common.validate_list(v, BACKUP_FREQUENCIES, "Backup frequency")


class BackupState(BaseModel):
    last_run: Optional[int] = None


class BatchSettings(BaseModel):
    ids: List[str]
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
    domain: Optional[str] = ""
    https: Optional[bool] = True


class ConfiguratorCoinDescription(BaseModel):
    enabled: Optional[bool] = True
    network: Optional[str] = "mainnet"
    lightning: Optional[bool] = False


class ConfiguratorAdvancedSettings(BaseModel):
    installation_pack: Optional[str] = "all"
    bitcart_docker_repository: Optional[str] = ""
    additional_components: Optional[List[str]] = []


class ConfiguratorSSHSettings(BaseModel):
    host: Optional[str]
    username: Optional[str]
    password: Optional[str]
    root_password: Optional[str]


class ConfiguratorServerSettings(BaseModel):
    domain_settings: Optional[ConfiguratorDomainSettings] = ConfiguratorDomainSettings()
    coins: Optional[Dict[str, ConfiguratorCoinDescription]] = {}
    additional_services: Optional[List[str]] = []
    advanced_settings: Optional[ConfiguratorAdvancedSettings] = ConfiguratorAdvancedSettings()


class ConfiguratorDeploySettings(ConfiguratorServerSettings):
    mode: str
    ssh_settings: Optional[ConfiguratorSSHSettings] = ConfiguratorSSHSettings()


# This is different from ConfiguratorSSHSettings - it is an internal object which is used for ssh connection management
# throughout the app
class SSHSettings(BaseModel):
    host: Optional[str]
    port: Optional[int] = 22
    username: Optional[str]
    password: Optional[str]
    key_file: Optional[str]
    key_file_password: Optional[str]
    authorized_keys_file: Optional[str]
    bash_profile_script: Optional[str]

    def create_ssh_client(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs = dict(hostname=self.host, port=self.port, username=self.username, allow_agent=False, look_for_keys=False)
        if self.key_file:
            kwargs.update(key_filename=self.key_file, passphrase=self.key_file_password)
        else:
            kwargs.update(password=self.password)
        client.connect(**kwargs)
        return client
