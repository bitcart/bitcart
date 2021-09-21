import secrets
from datetime import timedelta

from bitcart.errors import BaseError as BitcartBaseError
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from gino.crud import UpdateRequest
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

    async def validate(self, **kwargs):
        from api import utils

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
                    raise HTTPException(403, "Access denied: attempt to use objects not owned by current user")

    @classmethod
    def process_kwargs(cls, kwargs):
        return kwargs

    @classmethod
    def prepare_create(cls, kwargs):
        from api import utils

        kwargs["id"] = utils.common.unique_id()
        return kwargs

    @classmethod
    def prepare_edit(cls, kwargs):
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

    async def add_fields(self):
        await super().add_fields()
        from api import utils

        success, self.balance = await utils.wallets.get_confirmed_wallet_balance(self)
        self.error = not success

    async def validate(self, **kwargs):
        await super().validate(**kwargs)
        if "xpub" in kwargs:
            currency = kwargs.get("currency", self.currency)
            coin = settings.get_coin(currency)
            try:
                if not await coin.validate_key(kwargs["xpub"]):
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

    JSON_KEYS = {"checkout_settings": schemes.StoreCheckoutSettings}

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
    templates = Column(JSON)
    user_id = Column(Text, ForeignKey(User.id, ondelete="SET NULL"))
    created = Column(DateTime(True), nullable=False)


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
    price = Column(Numeric(16, 8), nullable=False)
    quantity = Column(Numeric(16, 8), nullable=False)
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


class ProductxInvoice(BaseModel):
    __tablename__ = "productsxinvoices"

    product_id = Column(Text, ForeignKey("products.id", ondelete="SET NULL"))
    invoice_id = Column(Text, ForeignKey("invoices.id", ondelete="SET NULL"))
    count = Column(Integer)


class PaymentMethod(BaseModel):
    __tablename__ = "paymentmethods"

    id = Column(Text, primary_key=True, index=True)
    invoice_id = Column(Text, ForeignKey("invoices.id", ondelete="SET NULL"))
    amount = Column(Numeric(16, 8), nullable=False)
    rate = Column(Numeric(16, 8))
    discount = Column(Text)
    confirmations = Column(Integer, nullable=False)
    recommended_fee = Column(Numeric(16, 8), nullable=False)
    currency = Column(Text, index=True)
    payment_address = Column(Text, nullable=False)
    payment_url = Column(Text, nullable=False)
    rhash = Column(Text)
    lightning = Column(Boolean(), default=False)
    node_id = Column(Text)
    label = Column(Text)
    created = Column(DateTime(True), nullable=False)

    async def to_dict(self, index: int = None):
        from api import utils

        data = super().to_dict()
        invoice_id = data.pop("invoice_id")
        invoice = await utils.database.get_object(Invoice, invoice_id, load_data=False)  # To avoid recursion
        data["amount"] = currency_table.format_currency(self.currency, self.amount)
        data["rate"] = currency_table.format_currency(invoice.currency, self.rate, fancy=False)
        data["rate_str"] = currency_table.format_currency(invoice.currency, self.rate)
        data["name"] = self.get_name(index)
        return data

    def get_name(self, index: int = None):
        if self.label:
            return self.label
        name = f"{self.currency} (⚡)" if self.lightning else self.currency
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
    price = Column(Numeric(16, 8), nullable=False)
    currency = Column(Text)
    paid_currency = Column(Text)
    status = Column(Text, nullable=False)
    expiration = Column(Integer)
    buyer_email = Column(Text)
    discount = Column(Text)
    promocode = Column(Text)
    notification_url = Column(Text)
    redirect_url = Column(Text)
    store_id = Column(
        Text,
        ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"),
        index=True,
    )
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
