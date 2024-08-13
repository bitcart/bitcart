import math
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Literal, Optional, Union

import paramiko
from fastapi.exceptions import HTTPException
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, EmailStr, Field, PlainSerializer, field_validator, model_validator

from api.constants import BACKUP_FREQUENCIES, BACKUP_PROVIDERS, FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
from api.ext.moneyformat import currency_table
from api.types import Money, StrEnum

NonZuluDatetime = Annotated[datetime, PlainSerializer(lambda v: v.isoformat(), return_type=str, when_used="json")]
DecimalAsFloat = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


# Base setup for all models
class WorkingMode(StrEnum):
    UNSET = "unset"
    CREATE = "create"
    UPDATE = "update"
    DISPLAY = "display"  # no restrictions


def iter_attributes(obj):  # to do the from_attributes job because pydantic doesn't do it before validator
    for k in dir(obj):
        if not k.startswith("_"):
            v = getattr(obj, k)
            if not callable(v):
                yield k, v


class BaseModel(PydanticBaseModel):
    MODE: ClassVar[str] = WorkingMode.UNSET

    @staticmethod
    def _prepare_value(v):
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(
        mode="wrap"
    )  # TODO: wrap used here due to pydantic bug: https://github.com/pydantic/pydantic/issues/10135
    @classmethod
    def remove_hidden(cls, values, handler):
        if cls.MODE == WorkingMode.UNSET:  # pragma: no cover
            raise ValueError("Base model should not be used directly")
        if not isinstance(values, dict):
            values = {k: cls._prepare_value(v) for k, v in iter_attributes(values)}
        if cls.MODE == WorkingMode.DISPLAY:
            values = {k: cls._prepare_value(v) for k, v in values.items()}
        else:
            # We also skip empty strings (to trigger defaults) as that's what frontend sends
            values = {
                k: cls._prepare_value(v)
                for k, v in values.items()
                if k in cls.model_json_schema()["properties"] and (cls.MODE == WorkingMode.UPDATE or v != "")
            }
        return handler(values)

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

    model_config = ConfigDict(json_schema_extra=schema_extra)


class CreateModel(BaseModel):
    MODE: ClassVar[str] = WorkingMode.CREATE


class UpdateModel(BaseModel):
    MODE: ClassVar[str] = WorkingMode.UPDATE


class DisplayModel(BaseModel):
    MODE: ClassVar[str] = WorkingMode.DISPLAY


class CreatedMixin(BaseModel):
    metadata: dict[str, Any] = {}
    created: NonZuluDatetime = Field(
        None, json_schema_extra={"hidden": True}, validate_default=True
    )  # set by validator due to circular imports

    @field_validator("created", mode="before")
    @classmethod
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

    model_config = ConfigDict(from_attributes=True)


class CreateUser(CreateModel, BaseUser):
    password: str
    captcha_code: str = ""
    sso_type: str = "password"


class User(UpdateModel, BaseUser):
    password: str
    is_verified: bool
    is_enabled: bool


class DisplayUser(DisplayModel, BaseUser):
    id: str
    is_verified: bool
    is_enabled: bool
    sso_type: Optional[str] = None
    totp_key: str
    totp_url: str
    tfa_enabled: bool
    fido2_devices: list


class DisplayUserWithToken(DisplayUser):
    token: Optional[str] = None


# Tokens
class HTTPCreateToken(CreatedMixin):
    app_id: str = ""
    redirect_url: str = ""
    permissions: list[str] = []

    model_config = ConfigDict(from_attributes=True)


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
    currency: str = Field("btc", validate_default=True)
    lightning_enabled: bool = False
    label: str = ""
    hint: str = ""
    contract: str = ""
    additional_xpub_data: dict = {}

    model_config = ConfigDict(from_attributes=True)

    @field_validator("currency")
    @classmethod
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

    @model_validator(mode="before")
    @classmethod
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

    @field_validator("auth_mode")
    @classmethod
    def validate_auth_mode(cls, v):
        if v not in SMTPAuthMode:
            raise HTTPException(422, f"Invalid auth_mode. Expected either of {', '.join(SMTPAuthMode)}.")
        return v


class StoreCheckoutSettings(DisplayModel):
    expiration: int = 15
    transaction_speed: int = 0
    underpaid_percentage: float = 0
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

    @field_validator("recommended_fee_target_blocks")
    @classmethod
    def validate_recommended_fee_target_blocks(cls, v):
        from api import utils

        return utils.common.validate_list(v, FEE_ETA_TARGETS, "Recommended fee confirmation target blocks")

    @field_validator("transaction_speed")
    @classmethod
    def validate_transaction_speed(cls, v):
        if v < 0 or v > MAX_CONFIRMATION_WATCH:
            raise HTTPException(422, f"Transaction speed must be in range from 0 to {MAX_CONFIRMATION_WATCH}")
        return v

    @field_validator("underpaid_percentage")
    @classmethod
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
    default_currency: str = Field("USD", validate_default=True)
    checkout_settings: StoreCheckoutSettings = StoreCheckoutSettings()
    theme_settings: StoreThemeSettings = StoreThemeSettings()

    model_config = ConfigDict(from_attributes=True)

    @field_validator("default_currency")
    @classmethod
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
    end_date: NonZuluDatetime
    description: str = ""
    promocode: str = ""
    currencies: str = ""

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class UpdateNotification(UpdateModel, CreateNotification):
    pass


class DisplayNotification(DisplayModel, CreateNotification):
    id: str
    user_id: str
    error: bool = False


# Templates
class CreateTemplate(CreateModel, CreatedMixin):
    name: str
    text: str

    model_config = ConfigDict(from_attributes=True)


class UpdateTemplate(UpdateModel, CreateTemplate):
    pass


class DisplayTemplate(DisplayModel, CreateTemplate):
    id: str
    user_id: str


# Products
class CreateProduct(CreateModel, CreatedMixin):
    name: str
    price: DecimalAsFloat
    quantity: int
    store_id: str
    status: str = Field("active", json_schema_extra={"hidden_create": True})
    download_url: str = ""
    description: str = ""
    category: str = ""
    image: str = ""
    discounts: list[str] = []
    templates: dict[str, str] = {}

    model_config = ConfigDict(from_attributes=True)


class UpdateProduct(UpdateModel, CreateProduct):
    pass


class DisplayProduct(DisplayModel, CreateProduct):
    id: str
    user_id: str
    store_id: Optional[str]
    price: Money

    @model_validator(mode="before")
    @classmethod
    def set_price(cls, values):
        if "price" in values:
            values["price"] = currency_table.format_decimal(values.get("currency"), values["price"])
        return values


# Invoices
class CreateInvoice(CreateModel, CreatedMixin):
    price: DecimalAsFloat = Field(..., json_schema_extra={"hidden_update": True})
    store_id: str = Field(..., json_schema_extra={"hidden_update": True})
    currency: str = Field("", json_schema_extra={"hidden_update": True}, validate_default=True)
    order_id: str = ""
    notification_url: Optional[str] = ""
    redirect_url: Optional[str] = ""
    buyer_email: Optional[Union[EmailStr, Literal[""]]] = ""
    promocode: Optional[str] = Field("", json_schema_extra={"hidden_update": True})
    shipping_address: str = ""
    notes: str = ""
    status: str = Field(None, json_schema_extra={"hidden": True}, validate_default=True)
    exception_status: str = Field(None, json_schema_extra={"hidden": True}, validate_default=True)
    products: Union[list[str], dict[str, int]] = Field({}, json_schema_extra={"hidden_update": True})
    tx_hashes: list[str] = Field([], json_schema_extra={"hidden": True})
    expiration: int = Field(None, json_schema_extra={"hidden_update": True})
    sent_amount: DecimalAsFloat = Field(Decimal("0"), json_schema_extra={"hidden": True})

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v):
        return v.upper()

    @field_validator("status", mode="before")
    @classmethod
    def set_status(cls, v):
        from api.invoices import InvoiceStatus

        return v or InvoiceStatus.PENDING

    @field_validator("exception_status", mode="before")
    @classmethod
    def set_exception_status(cls, v):
        from api.invoices import InvoiceExceptionStatus

        return v or InvoiceExceptionStatus.NONE

    model_config = ConfigDict(from_attributes=True)


class CustomerUpdateData(UpdateModel):
    buyer_email: Union[EmailStr, Literal[""]] = ""
    shipping_address: str = ""
    notes: str = ""


class MethodUpdateData(UpdateModel):
    id: str
    address: str


class UpdateInvoice(UpdateModel, CreateInvoice):
    pass


class PaymentData(DisplayModel):
    created: NonZuluDatetime
    recommended_fee: DecimalAsFloat

    model_config = ConfigDict(extra="allow")


class DisplayInvoice(DisplayModel, CreateInvoice):
    id: str
    user_id: str
    store_id: Optional[str]
    time_left: int
    expiration_seconds: int
    product_names: dict
    payments: list[PaymentData] = []
    paid_date: Optional[NonZuluDatetime]
    payment_id: Optional[str]
    refund_id: Optional[str]
    paid_currency: Optional[str]
    discount: Optional[str]
    price: Money

    @model_validator(mode="before")
    @classmethod
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
    amount: DecimalAsFloat
    destination: str
    store_id: str
    wallet_id: str
    currency: str = Field("", validate_default=True)
    notification_url: str = ""
    max_fee: Optional[DecimalAsFloat] = Field(None, validate_default=True)
    status: str = Field(None, json_schema_extra={"hidden": True}, validate_default=True)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v):
        return v.upper()

    @field_validator("status", mode="before")
    @classmethod
    def set_status(cls, v):
        from api.ext.payouts import PayoutStatus

        return v or PayoutStatus.PENDING

    @field_validator("max_fee", mode="before")
    @classmethod
    def set_max_fee(cls, v):
        return v or None

    model_config = ConfigDict(from_attributes=True)


class UpdatePayout(UpdateModel, CreatePayout):
    pass


class DisplayPayout(DisplayModel, CreatePayout):
    id: str
    user_id: str
    store_id: Optional[str]
    wallet_id: Optional[str]
    wallet_currency: Optional[str]
    used_fee: Optional[DecimalAsFloat]
    tx_hash: Optional[str]
    amount: Money

    @model_validator(mode="before")
    @classmethod
    def set_amount(cls, values):
        if "amount" in values:
            values["amount"] = currency_table.format_decimal(values.get("currency"), values["amount"])
        return values


# Refunds
class CreateRefund(CreateModel, CreatedMixin):
    amount: DecimalAsFloat
    currency: str
    wallet_id: str
    invoice_id: str

    model_config = ConfigDict(from_attributes=True)


class UpdateRefund(UpdateModel, CreateRefund):
    pass


class DisplayRefund(DisplayModel, CreateRefund):
    id: str
    user_id: str
    wallet_id: Optional[str]
    destination: Optional[str]
    wallet_currency: Optional[str] = None  # added at runtime
    payout_id: Optional[str]
    payout_status: Optional[str] = None
    tx_hash: Optional[str] = None


# Files
class CreateFile(CreateModel, CreatedMixin):
    model_config = ConfigDict(from_attributes=True)


class UpdateFile(UpdateModel, CreateFile):
    pass


class DisplayFile(DisplayModel, CreateFile):
    id: str
    user_id: str
    filename: str


# Misc schemes
class TxResponse(DisplayModel):
    date: Optional[NonZuluDatetime]
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
    use_html_templates: bool = False
    global_templates: dict[str, str] = {}
    explorer_urls: dict[str, str] = {}
    rpc_urls: dict[str, str] = Field({}, validate_default=True)
    email_settings: EmailSettings = EmailSettings()

    async def async_init(self):
        from api import settings

        for key in settings.settings.cryptos:
            if self.explorer_urls.get(key) is None:
                self.explorer_urls[key] = await settings.settings.get_default_explorer(key)
        for key in settings.settings.template_manager.templates_strings["global"]:
            if self.global_templates.get(key) is None:
                self.global_templates[key] = ""

    @field_validator("rpc_urls", mode="before")  # pragma: no cover
    @classmethod
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

    @field_validator("captcha_type")
    @classmethod
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

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        from api import utils

        return utils.common.validate_list(v, BACKUP_PROVIDERS, "Backup provider")

    @field_validator("frequency")
    @classmethod
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
    amount: DecimalAsFloat


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
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    root_password: Optional[str] = None


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
    host: Optional[str] = None
    port: Optional[int] = 22
    username: Optional[str] = None
    password: Optional[str] = None
    key_file: Optional[str] = None
    key_file_password: Optional[str] = None
    authorized_keys_file: Optional[str] = None
    bash_profile_script: Optional[str] = None

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
    amount: DecimalAsFloat
    currency: str
    admin_host: str
    send_email: bool = True


class SubmitRefundData(CreateModel):
    destination: str


class RateResult(DisplayModel):
    rate: Optional[DecimalAsFloat] = Field(..., validate_default=True)
    message: str

    @field_validator("rate", mode="before")
    @classmethod
    def set_rate(cls, v):  # pragma: no cover
        if math.isnan(v):
            return None
        return v


class RatesResponse(DisplayModel):
    rates: list[RateResult]


class EmailVerifyResponse(DisplayModel):
    success: bool
    token: Optional[str]
