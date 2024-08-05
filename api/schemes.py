import math
import warnings
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar, Optional, Union

from cryptography.utils import CryptographyDeprecationWarning
from fastapi.exceptions import HTTPException
from pydantic import BaseModel as PydanticBaseModel
from pydantic import EmailStr, Field, root_validator, validator

from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS, FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
from api.ext.moneyformat import currency_table
from api.types import Money, StrEnum

# https://github.com/paramiko/paramiko/issues/2419
with warnings.catch_warnings():
    warnings.filterwarnings(action="ignore", category=CryptographyDeprecationWarning)
    import paramiko


# Base setup for all models
class WorkingMode(StrEnum):
    UNSET = "unset"
    CREATE = "create"
    UPDATE = "update"
    DISPLAY = "display"  # no restrictions


class BaseModel(PydanticBaseModel):
    MODE: ClassVar[str] = WorkingMode.UNSET

    @root_validator(pre=True)
    def remove_hidden(cls, values):
        if cls.MODE == WorkingMode.UNSET:  # pragma: no cover
            raise ValueError("Base model should not be used directly")
        # We also skip empty strings (to trigger defaults) as that's what frontend sends
        return {k: v for k, v in values.items() if k in cls.schema()["properties"] and v != ""}

    class Config:

        @staticmethod
        def schema_extra(schema: dict, cls):
            properties = dict()
            if cls.MODE != WorkingMode.DISPLAY:
                for k, v in schema.get("properties", {}).items():
                    hidden_create = v.get("hidden_create", v.get("hidden", False))
                    hidden_update = v.get("hidden_update", v.get("hidden", False))
                    if (
                        cls.MODE == WorkingMode.CREATE
                        and not hidden_create
                        or cls.MODE == WorkingMode.UPDATE
                        and not hidden_update
                    ):
                        properties[k] = v
                schema["properties"] = properties


class CreateModel(BaseModel):
    MODE: ClassVar[str] = WorkingMode.CREATE


class UpdateModel(BaseModel):
    MODE: ClassVar[str] = WorkingMode.UPDATE


class DisplayModel(BaseModel):
    MODE: ClassVar[str] = WorkingMode.DISPLAY


class CreatedMixin(BaseModel):
    metadata: dict[str, Any] = {}
    created: datetime = Field(None, hidden=True)  # set by validator due to circular imports

    @validator("created", pre=True, always=True)
    def set_created(cls, v):
        from api.utils.time import now

        return v or now()


# Users
class UserPreferences(DisplayModel):
    balance_currency: str = "USD"
    fetch_balance: bool = True


class BaseUser(CreatedMixin):
    email: EmailStr
    is_superuser: bool = False
    settings: UserPreferences = UserPreferences()

    class Config:
        orm_mode = True


class CreateUser(CreateModel, BaseUser):
    password: str
    captcha_code: str = ""


class User(UpdateModel, BaseUser):
    password: str
    is_verified: bool
    is_enabled: bool


class DisplayUser(DisplayModel, BaseUser):
    id: str
    is_verified: bool
    is_enabled: bool
    totp_key: str
    totp_url: str
    tfa_enabled: bool
    fido2_devices: list


# Tokens
class HTTPCreateToken(CreatedMixin):
    app_id: str = ""
    redirect_url: str = ""
    permissions: list[str] = []

    class Config:
        orm_mode = True


class HTTPCreateLoginToken(CreateModel, HTTPCreateToken):
    email: EmailStr = ""
    password: str = ""
    captcha_code: str = ""
    strict: bool = True


class CreateDBToken(DisplayModel, HTTPCreateToken):
    user_id: str


class EditToken(UpdateModel):
    redirect_url: str = ""


class Token(CreateDBToken):
    id: str


# Auth stuff
class VerifyTOTP(DisplayModel):
    code: str


class TOTPAuth(VerifyTOTP):
    token: str


class FIDO2Auth(DisplayModel):
    token: str
    auth_host: str


class LoginFIDOData(DisplayModel):
    auth_host: str


class RegisterFidoData(DisplayModel):
    name: str


class ChangePassword(UpdateModel):
    old_password: str
    password: str
    logout_all: bool = False


class ResetPasswordData(UpdateModel):
    email: EmailStr
    captcha_code: str = ""


class VerifyEmailData(ResetPasswordData):
    pass


class ResetPasswordFinalize(UpdateModel):
    password: str
    logout_all: bool = True


# Wallets
class CreateWallet(CreateModel, CreatedMixin):
    name: str
    xpub: str
    currency: str = "btc"
    lightning_enabled: bool = False
    label: str = ""
    hint: str = ""
    contract: str = ""
    additional_xpub_data: dict = {}

    class Config:
        orm_mode = True

    @validator("currency", always=True)
    def validate_currency(cls, v):
        return v.lower()


# used for xpub generation
class CreateWalletData(CreateModel):
    currency: str
    hot_wallet: bool


class UpdateWallet(UpdateModel, CreateWallet):
    pass


class DisplayWallet(DisplayModel, UpdateWallet):
    id: str
    user_id: str
    balance: Money
    xpub_name: str
    error: bool = False

    @root_validator(pre=True)
    def set_balance(cls, values):
        if "balance" in values:
            values["balance"] = currency_table.format_decimal(
                values.get("currency"), values["balance"], divisibility=values.get("divisibility")
            )
        return values


# Stores
class SMTPAuthMode(StrEnum):
    NONE = "none"
    SSL_TLS = "ssl/tls"
    STARTTLS = "starttls"


class EmailSettings(DisplayModel):  # all policies have DisplayModel
    address: str = ""
    host: str = ""
    port: int = 25
    user: str = ""
    password: str = ""
    auth_mode: str = SMTPAuthMode.STARTTLS

    @validator("auth_mode")
    def validate_auth_mode(cls, v):
        if v not in SMTPAuthMode:
            raise HTTPException(422, f"Invalid auth_mode. Expected either of {', '.join(SMTPAuthMode)}.")
        return v


class StoreCheckoutSettings(DisplayModel):
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
    randomize_wallet_selection: bool = False
    allow_anonymous_invoice_creation: bool = True
    include_network_fee: bool = False
    rate_rules: str = ""
    pos_screen_enabled: bool = True

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


class StoreThemeSettings(DisplayModel):
    store_theme_url: str = ""
    checkout_theme_url: str = ""


class StoreShopifySettings(DisplayModel):
    shop_name: str = ""
    api_key: str = ""
    api_secret: str = ""


class StorePluginSettings(DisplayModel):
    shopify: StoreShopifySettings = StoreShopifySettings()


class BaseStore(CreatedMixin):
    name: str
    default_currency: str = "USD"
    checkout_settings: StoreCheckoutSettings = StoreCheckoutSettings()
    theme_settings: StoreThemeSettings = StoreThemeSettings()

    class Config:
        orm_mode = True

    @validator("default_currency", always=True)
    def validate_default_currency(cls, v):
        return v.upper()


class CreateStore(CreateModel, BaseStore):
    wallets: list[str]
    notifications: list[str] = []
    templates: dict[str, str] = {}
    email_settings: EmailSettings = EmailSettings()
    plugin_settings: StorePluginSettings = StorePluginSettings()


class UpdateStore(UpdateModel, CreateStore):
    pass


class PublicStore(DisplayModel, BaseStore):
    id: str
    user_id: str
    currency_data: dict


class DisplayStore(DisplayModel, CreateStore):
    id: str
    user_id: str
    currency_data: dict


# Discounts
class CreateDiscount(CreateModel, CreatedMixin):
    name: str
    percent: int
    end_date: datetime
    description: str = ""
    promocode: str = ""
    currencies: str = ""

    class Config:
        orm_mode = True


class UpdateDiscount(UpdateModel, CreateDiscount):
    pass


class DisplayDiscount(DisplayModel, CreateDiscount):
    id: str
    user_id: str


# Notifications
class CreateNotification(CreateModel, CreatedMixin):
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


class UpdateNotification(UpdateModel, CreateNotification):
    pass


class DisplayNotification(DisplayModel, CreateNotification):
    id: str
    user_id: str


# Templates
class CreateTemplate(CreateModel, CreatedMixin):
    name: str
    text: str

    class Config:
        orm_mode = True


class UpdateTemplate(UpdateModel, CreateTemplate):
    pass


class DisplayTemplate(DisplayModel, CreateTemplate):
    id: str
    user_id: str


# Products
class CreateProduct(CreateModel, CreatedMixin):
    name: str
    price: Decimal
    quantity: int
    store_id: Optional[str]
    status: str = Field("active", hidden_create=True)
    download_url: str = ""
    description: str = ""
    category: str = ""
    image: str = ""
    discounts: list[str] = []
    templates: dict[str, str] = {}

    class Config:
        orm_mode = True


class UpdateProduct(UpdateModel, CreateProduct):
    pass


class DisplayProduct(DisplayModel, CreateProduct):
    id: str
    user_id: str
    price: Money

    @root_validator(pre=True)
    def set_price(cls, values):
        if "price" in values:
            values["price"] = currency_table.format_decimal(values.get("currency"), values["price"])
        return values


# Invoices
class CreateInvoice(CreateModel, CreatedMixin):
    price: Decimal = Field(..., hidden_update=True)
    store_id: str = Field(..., hidden_update=True)
    currency: str = Field("", hidden_update=True)
    order_id: str = ""
    notification_url: str = ""
    redirect_url: str = ""
    buyer_email: Optional[EmailStr] = ""
    promocode: str = Field("", hidden_update=True)
    shipping_address: str = ""
    notes: str = ""
    status: str = Field(None, hidden=True)
    exception_status: str = Field(None, hidden=True)
    products: Union[list[str], dict[str, int]] = Field({}, hidden_update=True)
    tx_hashes: list[str] = Field([], hidden=True)
    expiration: int = Field(None, hidden_update=True)
    sent_amount: Decimal = Field(0, hidden=True)

    @validator("currency", always=True)
    def validate_currency(cls, v):
        return v.upper()

    @validator("status", pre=True, always=True)
    def set_status(cls, v):
        from api.invoices import InvoiceStatus

        return v or InvoiceStatus.PENDING

    @validator("exception_status", pre=True, always=True)
    def set_exception_status(cls, v):
        from api.invoices import InvoiceExceptionStatus

        return v or InvoiceExceptionStatus.NONE

    class Config:
        orm_mode = True


class CustomerUpdateData(UpdateModel):
    buyer_email: EmailStr = ""
    shipping_address: str = ""
    notes: str = ""


class MethodUpdateData(UpdateModel):
    id: str
    address: str


class UpdateInvoice(UpdateModel, CreateInvoice):
    pass


class DisplayInvoice(DisplayModel, CreateInvoice):
    id: str
    user_id: str
    time_left: int
    expiration_seconds: int
    product_names: dict
    payments: list = []
    paid_date: Optional[datetime]
    payment_id: Optional[str]
    refund_id: Optional[str]
    paid_currency: Optional[str]
    discount: Optional[str]
    price: Money

    @root_validator(pre=True)
    def set_price(cls, values):
        from api import crud

        if "price" in values:
            values["price"] = currency_table.format_decimal(values.get("currency"), values["price"])
        if "sent_amount" in values:
            values["sent_amount"] = currency_table.format_decimal(
                "",
                values["sent_amount"],
                divisibility=crud.invoices.find_sent_amount_divisibility(
                    values["id"], values["payments"], values["payment_id"]
                ),
            )
        return values


# Payouts
class CreatePayout(CreateModel, CreatedMixin):
    amount: Decimal
    destination: str
    store_id: str
    wallet_id: Optional[str]
    currency: str = ""
    notification_url: str = ""
    max_fee: Optional[Decimal] = None
    status: str = Field(None, hidden=True)

    @validator("currency", always=True)
    def validate_currency(cls, v):
        return v.upper()

    @validator("status", pre=True, always=True)
    def set_status(cls, v):
        from api.ext.payouts import PayoutStatus

        return v or PayoutStatus.PENDING

    @validator("max_fee", pre=True, always=True)
    def set_max_fee(cls, v):
        return v or None

    class Config:
        orm_mode = True


class UpdatePayout(UpdateModel, CreatePayout):
    pass


class DisplayPayout(DisplayModel, CreatePayout):
    id: str
    user_id: str
    wallet_currency: Optional[str]
    used_fee: Optional[Decimal]
    tx_hash: Optional[str]
    amount: Money

    @root_validator(pre=True)
    def set_amount(cls, values):
        if "amount" in values:
            values["amount"] = currency_table.format_decimal(values.get("currency"), values["amount"])
        return values


# Refunds
class CreateRefund(CreateModel, CreatedMixin):
    amount: Decimal
    currency: str
    wallet_id: str
    invoice_id: str

    class Config:
        orm_mode = True


class UpdateRefund(UpdateModel, CreateRefund):
    pass


class DisplayRefund(DisplayModel, CreateRefund):
    id: str
    user_id: str
    destination: Optional[str]
    wallet_currency: Optional[str]
    payout_id: Optional[str]
    payout_status: Optional[str]
    tx_hash: Optional[str]


# Files
class CreateFile(CreateModel, CreatedMixin):
    class Config:
        orm_mode = True


class UpdateFile(UpdateModel, CreateFile):
    pass


class DisplayFile(DisplayModel, CreateFile):
    id: str
    user_id: str
    filename: str


# Misc schemes
class TxResponse(DisplayModel):
    date: Optional[datetime]
    txid: str
    amount: str


class BalanceResponse(DisplayModel):
    confirmed: Money
    unconfirmed: Money
    unmatured: Money
    lightning: Money


class CaptchaType(StrEnum):
    NONE = "none"
    HCAPTCHA = "hcaptcha"
    CF_TURNSTILE = "cloudflare_turnstile"


class Policy(DisplayModel):
    _SECRET_FIELDS = {"captcha_secretkey", "email_settings"}

    disable_registration: bool = False
    require_verified_email: bool = False
    allow_file_uploads: bool = True
    discourage_index: bool = False
    check_updates: bool = True
    staging_updates: bool = False
    allow_anonymous_configurator: bool = True
    captcha_sitekey: str = ""
    captcha_secretkey: str = ""
    admin_theme_url: str = ""
    captcha_type: str = CaptchaType.NONE
    explorer_urls: dict[str, str] = {}
    rpc_urls: dict[str, str] = {}
    email_settings: EmailSettings = EmailSettings()

    async def async_init(self):
        from api import settings

        for key in settings.settings.cryptos:
            if self.explorer_urls.get(key) is None:
                self.explorer_urls[key] = await settings.settings.get_default_explorer(key)

    @validator("rpc_urls", pre=True, always=True)  # pragma: no cover
    def set_rpc_urls(cls, v):
        from api import settings

        if not v:
            v = {}
        for key in settings.settings.cryptos:
            if not settings.settings.cryptos[key].is_eth_based or settings.settings.cryptos[key].coin_name in ("TRX", "XMR"):
                continue
            if v.get(key) is None:
                v[key] = settings.settings.get_default_rpc(key)
        return v

    @validator("captcha_type")
    def validate_captcha_type(cls, v):
        if v not in CaptchaType:
            raise HTTPException(422, f"Invalid captcha_type. Expected either of {', '.join(CaptchaType)}.")
        return v


class GlobalStorePolicy(DisplayModel):
    pos_id: str = ""


class BackupsPolicy(DisplayModel):
    provider: str = "local"
    scheduled: bool = False
    frequency: str = "weekly"
    environment_variables: dict[str, str] = {}

    @validator("provider")
    def validate_provider(cls, v):
        from api import utils

        return utils.common.validate_list(v, BACKUP_PROVIDERS, "Backup provider")

    @validator("frequency")
    def validate_frequency(cls, v):
        from api import utils

        return utils.common.validate_list(v, BACKUP_FREQUENCIES, "Backup frequency")


class BackupState(DisplayModel):
    last_run: Optional[int] = None


class BatchSettings(DisplayModel):
    ids: list[str]
    command: str
    options: Optional[dict] = {}


class OpenChannelScheme(DisplayModel):
    node_id: str
    amount: Decimal


class CloseChannelScheme(DisplayModel):
    channel_point: str
    force: bool = False


class LNPayScheme(DisplayModel):
    invoice: str


class EventSystemMessage(DisplayModel):
    event: str
    data: dict


class ConfiguratorDomainSettings(DisplayModel):
    domain: Optional[str] = ""
    https: Optional[bool] = True


class ConfiguratorCoinDescription(DisplayModel):
    enabled: Optional[bool] = True
    network: Optional[str] = "mainnet"
    lightning: Optional[bool] = False


class ConfiguratorAdvancedSettings(DisplayModel):
    installation_pack: Optional[str] = "all"
    bitcart_docker_repository: Optional[str] = ""
    additional_components: Optional[list[str]] = []


class ConfiguratorSSHSettings(DisplayModel):
    host: Optional[str]
    username: Optional[str]
    password: Optional[str]
    root_password: Optional[str]


class ConfiguratorServerSettings(DisplayModel):
    domain_settings: Optional[ConfiguratorDomainSettings] = ConfiguratorDomainSettings()
    coins: Optional[dict[str, ConfiguratorCoinDescription]] = {}
    additional_services: Optional[list[str]] = []
    advanced_settings: Optional[ConfiguratorAdvancedSettings] = ConfiguratorAdvancedSettings()


class ConfiguratorDeploySettings(ConfiguratorServerSettings):
    mode: str
    ssh_settings: Optional[ConfiguratorSSHSettings] = ConfiguratorSSHSettings()


# This is different from ConfiguratorSSHSettings - it is an internal object which is used for ssh connection management
# throughout the app
class SSHSettings(DisplayModel):
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


class UninstallPluginData(DisplayModel):
    author: str
    name: str


class RefundData(DisplayModel):
    amount: Decimal
    currency: str
    admin_host: str
    send_email: bool = True


class SubmitRefundData(CreateModel):
    destination: str


class RateResult(DisplayModel):
    rate: Optional[Decimal]
    message: str

    @validator("rate", pre=True, always=True)
    def set_rate(cls, v):  # pragma: no cover
        if math.isnan(v):
            return None
        return v


class RatesResponse(DisplayModel):
    rates: list[RateResult]


class EmailVerifyResponse(DisplayModel):
    success: bool
    token: Optional[str]
