import inspect
import secrets
import sys
from datetime import timedelta

from bitcart.errors import BaseError as BitcartBaseError
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from gino.crud import UpdateRequest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import ARRAY

from api import schemes, settings
from api.constants import PUBLIC_ID_LENGTH
from api.db import db
from api.ext.moneyformat import currency_table
from api.logger import get_exception_message, get_logger

# shortcuts
Column = db.Column
Integer = db.Integer
Text = db.Text
Boolean = db.Boolean
Numeric = db.Numeric
DateTime = db.DateTime
Text = db.Text
ForeignKey = db.ForeignKey
JSON = db.JSON
UniqueConstraint = db.UniqueConstraint

logger = get_logger(__name__)


async def create_relations(model_id, related_ids, key_info):
    data = [{key_info["current_id"]: model_id, key_info["related_id"]: related_id} for related_id in related_ids]
    await key_info["table"].insert().gino.all(data)


async def delete_relations(model_id, key_info):
    await key_info["table"].delete.where(getattr(key_info["table"], key_info["current_id"]) == model_id).gino.status()


class BaseModel(db.Model):
    JSON_KEYS: dict = {}

    @property
    def M2M_KEYS(self):
        model_variant = getattr(self, "KEYS", {})
        update_variant = getattr(self._update_request_cls, "KEYS", {})
        return model_variant or update_variant

    async def create_related(self):
        for key in self.M2M_KEYS:
            related_ids = getattr(self, key, [])
            await create_relations(self.id, related_ids, self.M2M_KEYS[key])

    async def add_related(self):
        for key in self.M2M_KEYS:
            key_info = self.M2M_KEYS[key]
            result = (
                await key_info["table"]
                .select(key_info["related_id"])
                .where(getattr(key_info["table"], key_info["current_id"]) == self.id)
                .gino.all()
            )
            setattr(self, key, [obj_id for obj_id, in result if obj_id])

    async def delete_related(self):
        for key_info in self.M2M_KEYS.values():
            await delete_relations(self.id, key_info)

    async def add_fields(self):
        for field, scheme in self.JSON_KEYS.items():
            setattr(self, field, self.get_json_key(field, scheme))

    async def load_data(self):
        await self.add_related()
        await self.add_fields()

    async def _delete(self, *args, **kwargs):
        await self.delete_related()
        return await super()._delete(*args, **kwargs)

    @classmethod
    async def create(cls, **kwargs):
        model = await super().create(**kwargs)
        await model.create_related()
        await model.load_data()
        return model

    async def validate(self, kwargs):
        from api import utils

        fkey_columns = (col for col in self.__table__.columns if col.foreign_keys)
        exc = HTTPException(403, "Access denied: attempt to use objects not owned by current user")
        for col in fkey_columns:
            if col.name in kwargs:
                # we assume i.e. user_id -> User
                table_name = col.name.replace("_id", "").capitalize()
                if not await utils.database.get_object(
                    all_tables[table_name], kwargs[col.name], user_id=self.user_id, raise_exception=False
                ):
                    raise exc

        for key in self.M2M_KEYS:
            if key in kwargs:
                key_info = self.M2M_KEYS[key]
                related_ids = kwargs[key]
                count = await utils.database.get_scalar(
                    key_info["related_table"]
                    .query.where(key_info["related_table"].user_id == self.user_id)
                    .where(key_info["related_table"].id.in_(related_ids)),
                    db.func.count,
                    key_info["related_table"].id,
                )
                if count != len(related_ids):
                    raise exc

    @classmethod
    def process_kwargs(cls, kwargs):
        return kwargs

    @classmethod
    def prepare_create(cls, kwargs):
        from api import utils

        kwargs["id"] = utils.common.unique_id()
        return kwargs

    def prepare_edit(self, kwargs):
        kwargs.pop("user_id", None)  # don't allow changing ownership of objects
        return kwargs

    def get_json_key(self, key, scheme):
        data = getattr(self, key) or {}
        return scheme(**data)

    async def set_json_key(self, key, scheme):
        # Update only passed values, don't modify existing ones
        json_data = jsonable_encoder(getattr(self, key).copy(update=scheme.dict(exclude_unset=True)))
        kwargs = {key: json_data}
        await self.update(**kwargs).apply()


# Abstract class to easily implement many-to-many update behaviour


# NOTE: do NOT edit self, but self._instance instead - it is the target model
class ManyToManyUpdateRequest(UpdateRequest):
    KEYS: dict

    def update(self, **kwargs):
        for key in self.KEYS:
            if key in kwargs:
                setattr(self._instance, key, kwargs.pop(key))
        self.empty = not kwargs
        return super().update(**kwargs)

    async def apply(self):
        for key in self.KEYS:
            key_info = self.KEYS[key]
            data = getattr(self._instance, key, None)
            if data is None:  # pragma: no cover
                data = []
            else:
                await delete_relations(self._instance.id, key_info)
            await create_relations(self._instance.id, data, key_info)
            setattr(self._instance, key, data)
        if not self.empty:
            return await super().apply()


class User(BaseModel):
    __tablename__ = "users"

    JSON_KEYS = {"settings": schemes.UserPreferences}

    id = Column(Text, primary_key=True, index=True)
    email = Column(Text, unique=True, index=True)
    hashed_password = Column(Text)
    is_superuser = Column(Boolean(), default=False)
    created = Column(DateTime(True), nullable=False)
    settings = Column(JSON)

    @classmethod
    def process_kwargs(cls, kwargs):
        from api import utils

        kwargs = super().process_kwargs(kwargs)
        if "password" in kwargs:
            if kwargs["password"] is not None:
                kwargs["hashed_password"] = utils.authorization.get_password_hash(kwargs["password"])
            del kwargs["password"]
        return kwargs


class Wallet(BaseModel):
    __tablename__ = "wallets"

    id = Column(Text, primary_key=True, index=True)
    name = Column(Text, index=True)
    xpub = Column(Text, index=True)
    currency = Column(Text, index=True)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    created = Column(DateTime(True), nullable=False)
    lightning_enabled = Column(Boolean(), default=False)
    label = Column(Text)
    hint = Column(Text)
    contract = Column(Text)
    additional_xpub_data = Column(JSON)

    def prepare_edit(self, kwargs):  # pragma: no cover
        super().prepare_edit(kwargs)
        if "currency" in kwargs and "additional_xpub_data" not in kwargs and self.provider != kwargs["currency"]:
            kwargs["additional_xpub_data"] = {}
        return kwargs

    async def add_fields(self):
        await super().add_fields()
        from api import utils

        success, self.divisibility, self.balance = await utils.wallets.get_confirmed_wallet_balance(self)
        self.error = not success

    @classmethod
    def process_kwargs(cls, kwargs):
        kwargs = super().process_kwargs(kwargs)
        kwargs.pop("divisibility", None)
        return kwargs

    async def validate(self, kwargs):
        await super().validate(kwargs)
        if any(key in kwargs for key in ("xpub", "contract", "additional_xpub_data")):
            currency = kwargs.get("currency", self.currency)
            coin = settings.settings.get_coin(currency)
            if "xpub" in kwargs or "additional_xpub_data" in kwargs:
                await self.validate_xpub(
                    coin,
                    currency,
                    kwargs.get("xpub", self.xpub),
                    kwargs.get("additional_xpub_data", self.additional_xpub_data),
                )
            if "contract" in kwargs and kwargs["contract"]:  # pragma: no cover
                tokens = await coin.server.get_tokens()
                kwargs["contract"] = tokens.get(kwargs["contract"], kwargs["contract"])
                try:
                    if not await coin.server.validatecontract(kwargs["contract"]):
                        raise HTTPException(422, "Contract invalid")
                    kwargs["contract"] = await coin.server.normalizeaddress(kwargs["contract"])
                except BitcartBaseError as e:
                    logger.error(f"Failed to validate contract for currency {currency}:\n{get_exception_message(e)}")
                    raise HTTPException(422, "Invalid contract")

    async def validate_xpub(self, coin, currency, xpub, additional_xpub_data):
        try:
            if not await coin.validate_key(xpub, **additional_xpub_data):
                raise HTTPException(422, "Wallet key invalid")
        except BitcartBaseError as e:
            logger.error(f"Failed to validate xpub for currency {currency}:\n{get_exception_message(e)}")
            raise HTTPException(422, "Wallet key invalid")


class Notification(BaseModel):
    __tablename__ = "notifications"

    id = Column(Text, primary_key=True, index=True)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    name = Column(Text, index=True)
    provider = Column(Text)
    data = Column(JSON)
    created = Column(DateTime(True), nullable=False)

    def prepare_edit(self, kwargs):
        super().prepare_edit(kwargs)
        if "provider" in kwargs and "data" not in kwargs and self.provider != kwargs["provider"]:
            kwargs["data"] = {}
        return kwargs


class Template(BaseModel):
    __tablename__ = "templates"

    id = Column(Text, primary_key=True, index=True)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    name = Column(Text, index=True)
    text = Column(Text())
    created = Column(DateTime(True), nullable=False)
    _unique_constaint = UniqueConstraint("user_id", "name")


class WalletxStore(BaseModel):
    __tablename__ = "walletsxstores"

    wallet_id = Column(Text, ForeignKey("wallets.id", ondelete="SET NULL"))
    store_id = Column(Text, ForeignKey("stores.id", ondelete="SET NULL"))


class NotificationxStore(BaseModel):
    __tablename__ = "notificationsxstores"

    notification_id = Column(Text, ForeignKey("notifications.id", ondelete="SET NULL"))
    store_id = Column(Text, ForeignKey("stores.id", ondelete="SET NULL"))


class StoreUpdateRequest(ManyToManyUpdateRequest):
    KEYS = {
        "wallets": {
            "table": WalletxStore,
            "current_id": "store_id",
            "related_id": "wallet_id",
            "related_table": Wallet,
        },
        "notifications": {
            "table": NotificationxStore,
            "current_id": "store_id",
            "related_id": "notification_id",
            "related_table": Notification,
        },
    }


class Store(BaseModel):
    __tablename__ = "stores"
    _update_request_cls = StoreUpdateRequest

    JSON_KEYS = {
        "checkout_settings": schemes.StoreCheckoutSettings,
        "theme_settings": schemes.StoreThemeSettings,
        "plugin_settings": schemes.StorePluginSettings,
    }

    id = Column(Text, primary_key=True, index=True)
    name = Column(Text, index=True)
    default_currency = Column(Text)
    email = Column(Text, index=True)
    email_host = Column(Text)
    email_password = Column(Text)
    email_port = Column(Integer)
    email_use_ssl = Column(Boolean)
    email_user = Column(Text)
    checkout_settings = Column(JSON)
    theme_settings = Column(JSON)
    plugin_settings = Column(JSON)
    templates = Column(JSON)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    created = Column(DateTime(True), nullable=False)

    async def add_fields(self):
        await super().add_fields()
        self.currency_data = currency_table.get_currency_data(self.default_currency)

    @classmethod
    def process_kwargs(cls, kwargs):
        kwargs = super().process_kwargs(kwargs)
        kwargs.pop("currency_data", None)
        return kwargs


class Discount(BaseModel):
    __tablename__ = "discounts"

    id = Column(Text, primary_key=True, index=True)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    name = Column(Text, index=True)
    percent = Column(Integer)
    description = Column(Text, index=True)
    promocode = Column(Text)
    currencies = Column(Text, index=True)
    end_date = Column(DateTime(True), nullable=False)
    created = Column(DateTime(True), nullable=False)


class DiscountxProduct(BaseModel):
    __tablename__ = "discountsxproducts"

    discount_id = Column(Text, ForeignKey("discounts.id", ondelete="SET NULL"))
    product_id = Column(Text, ForeignKey("products.id", ondelete="SET NULL"))


class ProductUpdateRequest(ManyToManyUpdateRequest):
    KEYS = {
        "discounts": {
            "table": DiscountxProduct,
            "current_id": "product_id",
            "related_id": "discount_id",
            "related_table": Discount,
        },
    }


class Product(BaseModel):
    __tablename__ = "products"
    _update_request_cls = ProductUpdateRequest

    id = Column(Text, primary_key=True, index=True)
    name = Column(Text, index=True)
    price = Column(Numeric(36, 18), nullable=False)
    quantity = Column(Numeric(36, 18), nullable=False)
    download_url = Column(Text)
    category = Column(Text)
    description = Column(Text)
    image = Column(Text)
    store_id = Column(
        Text,
        ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"),
        index=True,
    )
    status = Column(Text, nullable=False)
    templates = Column(JSON)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    created = Column(DateTime(True), nullable=False)

    @classmethod
    def prepare_create(cls, kwargs):
        from api import utils

        kwargs = super().prepare_create(kwargs)
        kwargs["id"] = utils.common.unique_id(PUBLIC_ID_LENGTH)
        return kwargs

    async def add_fields(self):
        await super().add_fields()
        from api import utils

        # TODO: rework logic of deleting related objects, maybe we need cascade delete?
        try:
            store = await utils.database.get_object(Store, self.store_id)
            self.currency = store.default_currency
        except HTTPException:  # for products associated with deleted stores
            self.currency = "USD"


class ProductxInvoice(BaseModel):
    __tablename__ = "productsxinvoices"

    product_id = Column(Text, ForeignKey("products.id", ondelete="SET NULL"))
    invoice_id = Column(Text, ForeignKey("invoices.id", ondelete="SET NULL"))
    count = Column(Integer)


class PaymentMethod(BaseModel):
    __tablename__ = "paymentmethods"

    id = Column(Text, primary_key=True, index=True)
    invoice_id = Column(Text, ForeignKey("invoices.id", ondelete="SET NULL"))
    amount = Column(Numeric(36, 18), nullable=False)
    rate = Column(Numeric(36, 18))
    discount = Column(Text)
    confirmations = Column(Integer, nullable=False)
    recommended_fee = Column(Numeric(36, 18), nullable=False)
    currency = Column(Text, index=True)
    symbol = Column(Text)
    payment_address = Column(Text, nullable=False)
    payment_url = Column(Text, nullable=False)
    rhash = Column(Text)
    lookup_field = Column(Text)
    lightning = Column(Boolean(), default=False)
    contract = Column(Text)
    divisibility = Column(Integer)
    node_id = Column(Text)
    label = Column(Text)
    hint = Column(Text)
    created = Column(DateTime(True), nullable=False)

    async def to_dict(self, index: int = None):
        from api import utils

        data = super().to_dict()
        invoice_id = data.pop("invoice_id")
        invoice = await utils.database.get_object(Invoice, invoice_id, load_data=False)  # To avoid recursion
        data["amount"] = currency_table.format_decimal(self.symbol, self.amount, divisibility=self.divisibility)
        data["rate"] = currency_table.format_decimal(invoice.currency, self.rate)
        data["rate_str"] = currency_table.format_currency(invoice.currency, self.rate)
        data["name"] = self.get_name(index)
        if data["payment_url"].startswith("ethereum:"):  # pragma: no cover
            data["chain_id"] = self.parse_chain_id(data["payment_url"])
        return data

    @classmethod
    def parse_chain_id(self, url):  # pragma: no cover
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

    def get_name(self, index: int = None):
        if self.label:
            return self.label
        name = f"{self.symbol} (⚡)" if self.lightning else self.symbol
        if index:
            name += f" ({index})"
        return name.upper()


class Invoice(BaseModel):
    __tablename__ = "invoices"

    KEYS = {
        "products": {
            "table": ProductxInvoice,
            "current_id": "invoice_id",
            "related_id": "product_id",
            "related_table": Product,
        },
    }

    id = Column(Text, primary_key=True, index=True)
    price = Column(Numeric(36, 18), nullable=False)
    currency = Column(Text)
    paid_currency = Column(Text)
    status = Column(Text, nullable=False)
    expiration = Column(Integer)
    buyer_email = Column(Text)
    discount = Column(Text)
    promocode = Column(Text)
    shipping_address = Column(Text)
    notes = Column(Text)
    notification_url = Column(Text)
    redirect_url = Column(Text)
    store_id = Column(
        Text,
        ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"),
        index=True,
    )
    tx_hashes = Column(ARRAY(Text))
    order_id = Column(Text)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    created = Column(DateTime(True), nullable=False)

    async def add_related(self):
        from api import crud

        self.payments = []
        payment_methods = (
            await PaymentMethod.query.where(PaymentMethod.invoice_id == self.id).order_by(PaymentMethod.created).gino.all()
        )
        for index, method in crud.invoices.get_methods_inds(payment_methods):
            self.payments.append(await method.to_dict(index))
        await super().add_related()

    async def create_related(self):
        # NOTE: we don't call super() here, as the ProductxInvoice creation is delegated to CRUD utils
        pass

    @classmethod
    def process_kwargs(cls, kwargs):
        kwargs = super().process_kwargs(kwargs)
        kwargs.pop("products", None)
        return kwargs

    @classmethod
    def prepare_create(cls, kwargs):
        from api import utils

        kwargs = super().prepare_create(kwargs)
        kwargs["id"] = utils.common.unique_id(PUBLIC_ID_LENGTH)
        return kwargs

    def add_invoice_expiration(self):
        from api import utils

        self.expiration_seconds = self.expiration * 60
        date = self.created + timedelta(seconds=self.expiration_seconds) - utils.time.now()
        self.time_left = utils.time.time_diff(date)

    async def add_fields(self):
        await super().add_fields()
        self.add_invoice_expiration()


class Setting(BaseModel):
    __tablename__ = "settings"

    id = Column(Text, primary_key=True, index=True)
    name = Column(Text)
    value = Column(Text)
    created = Column(DateTime(True), nullable=False)

    @classmethod
    def prepare_create(cls, kwargs):
        from api import utils

        kwargs = super().prepare_create(kwargs)
        kwargs["created"] = utils.time.now()
        return kwargs


class Token(BaseModel):
    __tablename__ = "tokens"

    id = Column(Text, primary_key=True, index=True)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"), index=True)
    app_id = Column(Text)
    redirect_url = Column(Text)
    permissions = Column(ARRAY(Text))
    created = Column(DateTime(True), nullable=False)

    @classmethod
    def prepare_create(cls, kwargs):
        kwargs = super().prepare_create(kwargs)
        kwargs["id"] = secrets.token_urlsafe()
        return kwargs


class Payout(BaseModel):
    __tablename__ = "payouts"

    id = Column(Text, primary_key=True, index=True)
    amount = Column(Numeric(36, 18), nullable=False)
    destination = Column(Text)
    currency = Column(Text)
    status = Column(Text, nullable=False)
    notification_url = Column(Text)
    store_id = Column(Text, ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True)
    wallet_id = Column(Text, ForeignKey("wallets.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True)
    max_fee = Column(Numeric(36, 18))
    tx_hash = Column(Text)
    used_fee = Column(Numeric(36, 18))
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    created = Column(DateTime(True), nullable=False)

    async def validate(self, kwargs):
        await super().validate(kwargs)
        if "destination" in kwargs or "wallet_id" in kwargs:
            wallet_currency = (
                await select([Wallet.currency]).where(Wallet.id == kwargs.get("wallet_id", self.wallet_id)).gino.scalar()
            )
            coin = settings.settings.get_coin(wallet_currency)
            if not await coin.server.validateaddress(kwargs.get("destination", self.destination)):
                raise HTTPException(422, "Invalid destination address")

    async def add_related(self):
        from api import utils

        await super().add_related()
        try:
            wallet = await utils.database.get_object(Wallet, self.wallet_id)
            self.wallet_currency = wallet.currency
        except HTTPException:
            self.wallet_currency = None


all_tables = {
    name: table
    for (name, table) in inspect.getmembers(sys.modules[__name__], inspect.isclass)
    if issubclass(table, BaseModel) and table is not BaseModel
}
