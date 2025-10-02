import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pyotp
from advanced_alchemy.base import SQLQuery
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from api.ext.moneyformat import currency_table
from api.schemas.base import Schema
from api.schemas.misc import EmailSettings
from api.schemas.stores import StoreCheckoutSettings, StorePluginSettings, StoreThemeSettings
from api.schemas.users import UserPreferences
from api.sqltypes import MutableModel

my_metadata = MetaData(
    naming_convention={
        "ix": "%(column_0_label)s_idx",
        "uq": "%(table_name)s_%(column_0_name)s_key",
        "ck": "%(table_name)s_%(constraint_name)s_check",
        "fk": "%(table_name)s_%(column_0_name)s_%(referred_table_name)s_fkey",
        "pk": "%(table_name)s_pkey",
    }
)

all_tables: dict[str, type["Model"]] = {}


class Model(SQLQuery):
    __abstract__ = True
    __allow_unmapped__ = True

    def __init_subclass__(cls, **kwargs: Any) -> None:  # pragma: no cover
        if hasattr(cls, "__tablename__"):
            is_public = hasattr(cls, "PUBLIC")
            if hasattr(cls, "TABLE_PREFIX"):
                cls.__tablename__ = f"plugin_{cls.TABLE_PREFIX}_{cls.__tablename__}"
            if is_public:
                cls.__table_args__ = {"extend_existing": True}
            all_tables[cls.__name__] = cls
        super().__init_subclass__(**kwargs)

    metadata = my_metadata

    async def set_json_key(self, key: str, scheme: Schema) -> None:
        current_model = getattr(self, key)
        updated_model = current_model.model_copy(update=scheme.model_dump(exclude_unset=True))
        setattr(self, key, updated_model)

    def update(self, **data: Any) -> None:
        for key, value in data.items():
            setattr(self, key, value)


def utc_now() -> datetime:
    from api import utils

    return utils.time.now()


class TimestampedModel(Model):
    __abstract__ = True

    created: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=utc_now)
    updated: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), onupdate=utc_now, default=None)


class IDModel(TimestampedModel):
    __abstract__ = True

    @staticmethod
    def id_generator() -> str:
        from api import utils

        return utils.common.unique_id()

    @declared_attr
    def id(cls) -> Mapped[str]:
        return mapped_column(Text, primary_key=True, index=True, default=lambda: cls.id_generator())

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, self.__class__) and self.id == __value.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        # We do this complex thing because we might be outside a session with
        # an expired object; typically when Sentry tries to serialize the object for
        # error reporting.
        # But basically, we want to show the ID if we have it.
        insp = inspect(self)
        if insp.identity is not None:
            id_value = insp.identity[0]
            return f"{self.__class__.__name__}(id={id_value!r})"
        return f"{self.__class__.__name__}(id=None)"

    @classmethod
    def generate_id(cls) -> str:
        from api import utils

        return utils.common.unique_id()


class MetadataMixin:
    __abstract__ = True

    meta: Mapped[dict[str, Any]] = mapped_column("metadata", MutableDict.as_mutable(JSONB()), default=dict)


class RecordModel(IDModel, MetadataMixin):
    __abstract__ = True


class User(RecordModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    is_superuser: Mapped[bool] = mapped_column(Boolean(), default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean(), default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean(), default=True)
    totp_key: Mapped[str] = mapped_column(Text)
    tfa_enabled: Mapped[bool] = mapped_column(Boolean(), default=False)
    recovery_codes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list)
    fido2_devices: Mapped[list[dict[str, Any]]] = mapped_column(MutableList.as_mutable(ARRAY(JSONB())), default=list)
    settings: Mapped[UserPreferences] = mapped_column(
        "settings",
        MutableModel(UserPreferences),
        default=UserPreferences,
    )

    @property
    def totp_url(self) -> str:
        return pyotp.TOTP(self.totp_key).provisioning_uri(self.email, issuer_name="Bitcart")

    @declared_attr
    def tokens(cls) -> Mapped[list["Token"]]:
        return relationship(
            "Token",
            lazy="raise",
            back_populates="user",
            foreign_keys="[Token.user_id]",
        )


class WalletxStore(Model):
    __tablename__ = "walletsxstores"

    wallet_id: Mapped[str] = mapped_column(Text, ForeignKey("wallets.id", ondelete="CASCADE"), primary_key=True)
    store_id: Mapped[str] = mapped_column(Text, ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)


class Wallet(RecordModel):
    __tablename__ = "wallets"

    name: Mapped[str] = mapped_column(Text, index=True)
    xpub: Mapped[str] = mapped_column(Text, index=True)
    currency: Mapped[str] = mapped_column(Text, index=True)
    lightning_enabled: Mapped[bool] = mapped_column(Boolean(), default=False)
    label: Mapped[str] = mapped_column(Text)
    hint: Mapped[str | None] = mapped_column(Text)  # TODO: eventually handle None vs "" better
    contract: Mapped[str | None] = mapped_column(Text)
    additional_xpub_data: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSONB()), default=dict)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    balance: Decimal
    divisibility: int
    error: bool
    xpub_name: str

    stores = relationship("Store", lazy="raise", secondary=WalletxStore.__table__, back_populates="wallets", viewonly=True)

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Wallet.user_id]")


class NotificationxStore(Model):
    __tablename__ = "notificationsxstores"

    notification_id: Mapped[str] = mapped_column(Text, ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True)
    store_id: Mapped[str] = mapped_column(Text, ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True)


class Notification(RecordModel):
    __tablename__ = "notifications"

    name: Mapped[str] = mapped_column(Text, index=True)
    provider: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSONB()), default=dict)

    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    stores = relationship(
        "Store", lazy="raise", secondary=NotificationxStore.__table__, back_populates="notifications", viewonly=True
    )

    error: bool

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Notification.user_id]")


class Template(RecordModel):
    __tablename__ = "templates"

    name: Mapped[str] = mapped_column(Text, index=True)
    text: Mapped[str] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    __table_args__ = (UniqueConstraint("user_id", "name"),)

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Template.user_id]")


class Store(RecordModel):
    __tablename__ = "stores"

    name: Mapped[str] = mapped_column(Text, index=True)
    default_currency: Mapped[str] = mapped_column(Text)
    email_settings: Mapped[EmailSettings] = mapped_column("email_settings", MutableModel(EmailSettings), default=EmailSettings)
    checkout_settings: Mapped[StoreCheckoutSettings] = mapped_column(
        "checkout_settings",
        MutableModel(StoreCheckoutSettings),
        default=StoreCheckoutSettings,
    )
    theme_settings: Mapped[StoreThemeSettings] = mapped_column(
        "theme_settings", MutableModel(StoreThemeSettings), default=StoreThemeSettings
    )
    plugin_settings: Mapped[StorePluginSettings] = mapped_column(
        "plugin_settings", MutableModel(StorePluginSettings), default=StorePluginSettings
    )
    templates: Mapped[dict[str, Any]] = mapped_column("templates", MutableDict.as_mutable(JSONB()), default=dict)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    wallets = relationship(
        "Wallet", lazy="raise", secondary=WalletxStore.__table__, back_populates="stores", cascade="save-update, merge"
    )
    notifications = relationship(
        "Notification",
        lazy="raise",
        secondary=NotificationxStore.__table__,
        back_populates="stores",
        cascade="save-update, merge",
    )

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Store.user_id]")

    @property
    def currency_data(self) -> dict[str, Any]:
        from api.ext.moneyformat import currency_table

        return currency_table.get_currency_data(self.default_currency)


class DiscountxProduct(Model):
    __tablename__ = "discountsxproducts"

    discount_id: Mapped[str] = mapped_column(Text, ForeignKey("discounts.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[str] = mapped_column(Text, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)


class Discount(RecordModel):
    __tablename__ = "discounts"

    name: Mapped[str] = mapped_column(Text, index=True)
    percent: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text, index=True)
    promocode: Mapped[str | None] = mapped_column(Text)
    currencies: Mapped[str | None] = mapped_column(Text, index=True)
    end_date: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    products = relationship(
        "Product", lazy="raise", secondary=DiscountxProduct.__table__, back_populates="discounts", viewonly=True
    )

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Discount.user_id]")


class ProductxInvoice(Model):
    __tablename__ = "productsxinvoices"

    product_id: Mapped[str] = mapped_column(Text, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    invoice_id: Mapped[str] = mapped_column(Text, ForeignKey("invoices.id", ondelete="CASCADE"), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)

    product = relationship(
        "Product", lazy="joined", cascade="save-update, merge"
    )  # TODO: how can we enable lazy="raise" here?
    invoice = relationship("Invoice", lazy="raise", back_populates="products_associations", cascade="save-update, merge")


class Product(RecordModel):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(Text, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    quantity: Mapped[int] = mapped_column(Integer)
    download_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    image: Mapped[str | None] = mapped_column(Text)
    store_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey(Store.id, deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(Text)
    templates: Mapped[dict[str, Any]] = mapped_column(MutableDict.as_mutable(JSONB()), default=dict)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    discounts = relationship(
        "Discount",
        lazy="raise",
        secondary=DiscountxProduct.__table__,
        back_populates="products",
        cascade="save-update, merge",
    )

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Product.user_id]")

    @declared_attr
    def store(cls) -> Mapped["Store"]:
        return relationship("Store", lazy="raise", foreign_keys="[Product.store_id]")

    @property
    def currency(self) -> str:
        return self.store.default_currency if self.store else "USD"


class PaymentMethod(RecordModel):
    __tablename__ = "paymentmethods"

    invoice_id: Mapped[str | None] = mapped_column(Text, ForeignKey("invoices.id", ondelete="SET NULL"))
    wallet_id: Mapped[str | None] = mapped_column(Text, ForeignKey("wallets.id", ondelete="SET NULL"))
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    rate: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    discount: Mapped[str | None] = mapped_column(Text)
    confirmations: Mapped[int] = mapped_column(Integer)
    recommended_fee: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    currency: Mapped[str] = mapped_column(Text, index=True)
    symbol: Mapped[str] = mapped_column(Text)
    payment_address: Mapped[str] = mapped_column(Text)
    payment_url: Mapped[str] = mapped_column(Text)
    rhash: Mapped[str | None] = mapped_column(Text)
    lookup_field: Mapped[str] = mapped_column(Text)
    lightning: Mapped[bool] = mapped_column(Boolean(), default=False)
    contract: Mapped[str | None] = mapped_column(Text)
    divisibility: Mapped[int] = mapped_column(Integer)
    user_address: Mapped[str | None] = mapped_column(Text)
    node_id: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    hint: Mapped[str | None] = mapped_column(Text)
    is_used: Mapped[bool] = mapped_column(Boolean(), default=False)

    invoice = relationship("Invoice", lazy="raise", back_populates="payments", foreign_keys="[PaymentMethod.invoice_id]")

    @declared_attr
    def wallet(cls) -> Mapped["Wallet"]:
        return relationship("Wallet", lazy="raise", foreign_keys="[PaymentMethod.wallet_id]")

    def to_payment_dict(self, currency: str, index: int | None = None) -> dict[str, Any]:
        data = super().to_dict()
        data["metadata"] = data.pop("meta", {})
        data["amount"] = currency_table.format_decimal(self.symbol, self.amount, divisibility=self.divisibility)
        data["rate"] = currency_table.format_decimal(currency, self.rate)
        data["rate_str"] = currency_table.format_currency(currency, self.rate)
        data["name"] = self.get_name(index)
        if data["payment_url"].startswith("ethereum:"):  # pragma: no cover
            data["chain_id"] = self.parse_chain_id(data["payment_url"])
        return data

    @classmethod
    def parse_chain_id(cls, url: str) -> int | None:  # pragma: no cover
        k = url.find("@")
        if k == -1:
            return None
        part = url[k + 1 :]
        chain_id = ""
        for i in range(len(part)):
            if not part[i].isdigit():
                break
            chain_id += part[i]
        return int(chain_id)

    def get_name(self, index: int | None = None) -> str:
        if self.label:
            return self.label
        name = f"{self.symbol} (⚡)" if self.lightning else self.symbol
        if index:
            name += f" ({index})"
        return name.upper()


class Invoice(RecordModel):
    __tablename__ = "invoices"

    price: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    sent_amount: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    exception_status: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text)
    paid_currency: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    expiration: Mapped[int] = mapped_column(Integer)
    buyer_email: Mapped[str | None] = mapped_column(Text)
    discount: Mapped[str | None] = mapped_column(Text)
    promocode: Mapped[str | None] = mapped_column(Text)
    shipping_address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    notification_url: Mapped[str | None] = mapped_column(Text)
    redirect_url: Mapped[str | None] = mapped_column(Text)
    store_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey(Store.id, deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True
    )
    tx_hashes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list)
    order_id: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    creation_time: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    paid_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    payment_methods: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list)

    payments = relationship(
        "PaymentMethod",
        lazy="raise",
        back_populates="invoice",
        cascade="save-update, merge",
        order_by="PaymentMethod.created",
    )
    # delete needed here as it's related to the association table directly
    products_associations: Mapped[list["ProductxInvoice"]] = relationship(
        "ProductxInvoice",
        lazy="raise",
        cascade="save-update, merge, delete, delete-orphan",
    )
    products: AssociationProxy[list[Product]] = association_proxy(
        "products_associations",
        "product",
        creator=lambda product_obj: ProductxInvoice(product=product_obj),
    )

    payment_id: str | None
    refund_id: str | None
    product_names: dict[str, str]

    @declared_attr
    def store(cls) -> Mapped["Store"]:
        return relationship("Store", lazy="raise", foreign_keys="[Invoice.store_id]")

    @declared_attr
    def refunds(cls) -> Mapped[list["Refund"]]:
        return relationship("Refund", lazy="raise", foreign_keys="[Refund.invoice_id]", viewonly=True)

    @property
    def expiration_seconds(self) -> int:
        return self.expiration * 60

    @property
    def time_left(self) -> int:
        from api import utils

        date = self.created + timedelta(seconds=self.expiration_seconds) - utils.time.now()

        return utils.time.time_diff(date)


class Setting(IDModel):
    __tablename__ = "settings"

    name: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)  # TODO: maybe jsonb?


class Token(RecordModel):
    __tablename__ = "tokens"

    @staticmethod
    def id_generator() -> str:
        return secrets.token_urlsafe()

    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"), index=True)
    app_id: Mapped[str | None] = mapped_column(Text)
    redirect_url: Mapped[str | None] = mapped_column(Text)
    permissions: Mapped[list[str]] = mapped_column(MutableList.as_mutable(ARRAY(Text)), default=list)

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Token.user_id]")


class File(RecordModel):
    __tablename__ = "files"

    filename: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[File.user_id]")


class Payout(RecordModel):
    __tablename__ = "payouts"

    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    destination: Mapped[str] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    notification_url: Mapped[str | None] = mapped_column(Text)
    store_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey(Store.id, deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True
    )
    wallet_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey(Wallet.id, deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True
    )
    max_fee: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    tx_hash: Mapped[str | None] = mapped_column(Text)
    used_fee: Mapped[Decimal | None] = mapped_column(Numeric(36, 18))
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Payout.user_id]")

    @declared_attr
    def store(cls) -> Mapped["Store"]:
        return relationship("Store", lazy="raise", foreign_keys="[Payout.store_id]")

    @declared_attr
    def wallet(cls) -> Mapped["Wallet"]:
        return relationship("Wallet", lazy="raise", foreign_keys="[Payout.wallet_id]")

    @property
    def wallet_currency(self) -> str | None:
        return self.wallet.currency if self.wallet else None


class Refund(RecordModel):
    __tablename__ = "refunds"

    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    currency: Mapped[str] = mapped_column(Text)
    wallet_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey(Wallet.id, deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True
    )
    invoice_id: Mapped[str | None] = mapped_column(Text, ForeignKey(Invoice.id, ondelete="SET NULL"), index=True)
    payout_id: Mapped[str | None] = mapped_column(Text, ForeignKey(Payout.id, ondelete="SET NULL"), index=True)
    destination: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey(User.id, ondelete="SET NULL"))

    @declared_attr
    def user(cls) -> Mapped["User"]:
        return relationship("User", lazy="raise", foreign_keys="[Refund.user_id]")

    @declared_attr
    def wallet(cls) -> Mapped["Wallet"]:
        return relationship("Wallet", lazy="raise", foreign_keys="[Refund.wallet_id]")

    @declared_attr
    def invoice(cls) -> Mapped["Invoice"]:
        return relationship("Invoice", lazy="raise", foreign_keys="[Refund.invoice_id]", back_populates="refunds")

    @declared_attr
    def payout(cls) -> Mapped["Payout"]:
        return relationship("Payout", lazy="raise", foreign_keys="[Refund.payout_id]")

    @property
    def payout_status(self) -> str | None:
        return self.payout.status if self.payout else None

    @property
    def tx_hash(self) -> str | None:
        return self.payout.tx_hash if self.payout else None

    @property
    def wallet_currency(self) -> str | None:
        return self.payout.wallet_currency if self.payout else None
