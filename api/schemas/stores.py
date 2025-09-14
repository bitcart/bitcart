from typing import Any, cast

from fastapi import HTTPException
from pydantic import Field, field_validator

from api.constants import FEE_ETA_TARGETS, MAX_CONFIRMATION_WATCH
from api.schemas.base import DecimalAsFloat, MetadataInput, MetadataOutput, Schema, TimestampedSchema
from api.schemas.misc import EmailSettings
from api.schemas.notifications import DisplayNotification
from api.schemas.wallets import InfoWallet


class StoreCheckoutSettings(Schema):
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
    def validate_recommended_fee_target_blocks(cls, v: int) -> int:
        from api import utils

        return utils.common.validate_list(v, FEE_ETA_TARGETS, "Recommended fee confirmation target blocks")

    @field_validator("transaction_speed")
    @classmethod
    def validate_transaction_speed(cls, v: int) -> int:
        if v < 0 or v > MAX_CONFIRMATION_WATCH:
            raise HTTPException(422, f"Transaction speed must be in range from 0 to {MAX_CONFIRMATION_WATCH}")
        return v

    @field_validator("underpaid_percentage")
    @classmethod
    def validate_underpaid_percentage(cls, v: DecimalAsFloat) -> float:
        if v < 0 or v >= 100:
            raise HTTPException(422, "Underpaid percentage must be in range from 0 to 99.99")
        return float(v)


class StoreThemeSettings(Schema):
    store_theme_url: str = ""
    checkout_theme_url: str = ""


class StoreShopifySettings(Schema):
    shop_name: str = ""
    api_key: str = ""
    api_secret: str = ""


class StorePluginSettings(Schema):
    shopify: StoreShopifySettings = StoreShopifySettings()


class BaseStore(MetadataInput):
    name: str
    default_currency: str = Field("USD", validate_default=True)
    checkout_settings: StoreCheckoutSettings = StoreCheckoutSettings()
    theme_settings: StoreThemeSettings = StoreThemeSettings()

    @field_validator("default_currency")
    @classmethod
    def validate_default_currency(cls, v: str) -> str:
        return v.upper()


class CreateStore(BaseStore):
    wallets: list[str]
    email_settings: EmailSettings = EmailSettings()
    notifications: list[str] = []
    templates: dict[str, str] = {}
    plugin_settings: StorePluginSettings = StorePluginSettings()


class UpdateStore(CreateStore):
    pass


class PublicStore(MetadataOutput, BaseStore, TimestampedSchema):
    id: str
    user_id: str
    currency_data: dict[str, Any]


class DisplayStore(MetadataOutput, CreateStore, TimestampedSchema):
    id: str
    user_id: str
    currency_data: dict[str, Any]

    @field_validator("wallets", mode="before")
    @classmethod
    def validate_wallets(cls, v: list[InfoWallet] | list[str]) -> list[str]:
        # this logic is needed because fastapi decides to validate twice...
        if isinstance(v, list) and all(isinstance(w, str) for w in v):
            return cast(list[str], v)
        return [cast(InfoWallet, w).id for w in v]

    @field_validator("notifications", mode="before")
    @classmethod
    def validate_notifications(cls, v: list[DisplayNotification] | list[str]) -> list[str]:
        if isinstance(v, list) and all(isinstance(n, str) for n in v):
            return cast(list[str], v)
        return [cast(DisplayNotification, n).id for n in v]
