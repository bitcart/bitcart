# pylint: disable=no-member
import secrets

from fastapi import HTTPException
from gino.crud import UpdateRequest
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from . import settings
from .db import db

# shortcuts
Column = db.Column
Integer = db.Integer
String = db.String
Text = db.Text
Boolean = db.Boolean
Numeric = db.Numeric
DateTime = db.DateTime
Text = db.Text
ForeignKey = db.ForeignKey
JSON = db.JSON
UniqueConstraint = db.UniqueConstraint


class User(db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_superuser = Column(Boolean(), default=False)


class Wallet(db.Model):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(length=1000), index=True)
    xpub = Column(String(length=1000), index=True)
    currency = Column(String(length=1000), index=True)
    balance = Column(Numeric(16, 8), default=0)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="wallets")

    @classmethod
    async def create(cls, **kwargs):
        kwargs["currency"] = kwargs.get("currency") or "btc"
        coin = settings.get_coin(kwargs.get("currency"))
        if await coin.validate_key(kwargs.get("xpub")):
            return await super().create(**kwargs)
        else:
            raise HTTPException(422, "Wallet key invalid")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="notifications")
    name = Column(String(length=1000), index=True)
    provider = Column(String(length=10000))
    data = Column(JSON)


class Template(db.Model):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="templates")
    name = Column(String(length=100000), index=True)
    text = Column(Text())
    _unique_constaint = UniqueConstraint("user_id", "name")


class WalletxStore(db.Model):
    __tablename__ = "walletsxstores"

    wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="SET NULL"))
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="SET NULL"))


class NotificationxStore(db.Model):
    __tablename__ = "notificationsxstores"

    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="SET NULL"))
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="SET NULL"))


class StoreUpdateRequest(UpdateRequest):
    def update(self, **kwargs):
        self.wallets = kwargs.pop("wallets", None)
        self.notifications = kwargs.pop("notifications", None)
        return super().update(**kwargs)

    async def apply(self):
        if self.wallets:
            await WalletxStore.delete.where(WalletxStore.store_id == self._instance.id).gino.status()
        if self.wallets is None:
            self.wallets = []
        for i in self.wallets:
            await WalletxStore.create(store_id=self._instance.id, wallet_id=i)
        self._instance.wallets = self.wallets
        if self.notifications:
            await NotificationxStore.delete.where(NotificationxStore.store_id == self._instance.id).gino.status()
        if self.notifications is None:
            self.notifications = []
        for i in self.notifications:
            await NotificationxStore.create(store_id=self._instance.id, notification_id=i)
        self._instance.notifications = self.notifications
        return await super().apply()


class Store(db.Model):
    __tablename__ = "stores"
    _update_request_cls = StoreUpdateRequest

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(1000), index=True)
    default_currency = Column(Text)
    email = Column(String(1000), index=True)
    email_host = Column(String(1000))
    email_password = Column(String(1000))
    email_port = Column(Integer)
    email_use_ssl = Column(Boolean)
    email_user = Column(String(1000))
    templates = Column(JSON)
    wallets = relationship("Wallet", secondary=WalletxStore)
    notifications = relationship("Notification", secondary=NotificationxStore)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="stores")


class Discount(db.Model):
    __tablename__ = "discounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="discounts")
    name = Column(String(length=1000), index=True)
    percent = Column(Integer)
    description = Column(Text, index=True)
    promocode = Column(Text)
    currencies = Column(String(length=10000), index=True)
    end_date = Column(DateTime(True), nullable=False)


class DiscountxProduct(db.Model):
    __tablename__ = "discountsxproducts"

    discount_id = Column(Integer, ForeignKey("discounts.id", ondelete="SET NULL"))
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"))


class DiscountXProductUpdateRequest(UpdateRequest):
    def update(self, **kwargs):
        self.discounts = kwargs.pop("discounts", None)
        return super().update(**kwargs)

    async def apply(self):
        if self.discounts:
            await DiscountxProduct.delete.where(DiscountxProduct.product_id == self._instance.id).gino.status()
        if self.discounts is None:
            self.discounts = []
        for i in self.discounts:
            await DiscountxProduct.create(product_id=self._instance.id, discount_id=i)
        self._instance.discounts = self.discounts
        return await super().apply()


class Product(db.Model):
    __tablename__ = "products"
    _update_request_cls = DiscountXProductUpdateRequest

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(length=1000), index=True)
    price = Column(Numeric(16, 8), nullable=False)
    quantity = Column(Numeric(16, 8), nullable=False)
    download_url = Column(String(100000))
    date = Column(DateTime(True), nullable=False)
    category = Column(Text)
    description = Column(Text)
    image = Column(String(100000))
    store_id = Column(
        Integer, ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True,
    )
    status = Column(String(1000), nullable=False)
    templates = Column(JSON)
    store = relationship("Store", back_populates="products")
    discounts = relationship("Discount", secondary=DiscountxProduct)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="products")


class ProductxInvoice(db.Model):
    __tablename__ = "productsxinvoices"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"))
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"))
    count = Column(Integer)


class MyUpdateRequest(UpdateRequest):
    def update(self, **kwargs):
        self.products = kwargs.pop("products", None)
        return super().update(**kwargs)

    async def apply(self):
        if self.products:
            await ProductxInvoice.delete.where(ProductxInvoice.invoice_id == self._instance.id).gino.status()
        if self.products is None:
            self.products = []
        for i in self.products:
            await ProductxInvoice.create(invoice_id=self._instance.id, product_id=i)
        self._instance.products = self.products
        return await super().apply()


class PaymentMethod(db.Model):
    __tablename__ = "paymentmethods"

    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"))
    amount = Column(Numeric(16, 8), nullable=False)
    discount = Column(Integer)
    currency = Column(String(length=1000), index=True)
    payment_address = Column(String(10000), nullable=False)
    payment_url = Column(String(10000), nullable=False)


class Invoice(db.Model):
    __tablename__ = "invoices"
    _update_request_cls = MyUpdateRequest

    id = Column(Integer, primary_key=True, index=True)
    price = Column(Numeric(16, 8), nullable=False)
    currency = Column(Text)
    status = Column(String(1000), nullable=False)
    date = Column(DateTime(True), nullable=False)
    buyer_email = Column(String(10000))
    discount = Column(Integer)
    promocode = Column(Text)
    notification_url = Column(Text)
    redirect_url = Column(Text)
    products = relationship("Product", secondary=ProductxInvoice)
    store_id = Column(
        Integer, ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"), index=True,
    )
    order_id = Column(Text)
    store = relationship("Store", back_populates="invoices")
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="invoices")

    @classmethod
    async def create(cls, **kwargs):
        from . import crud

        store_id = kwargs["store_id"]
        kwargs["status"] = "Pending"
        if not store_id:
            raise HTTPException(422, "No store id provided")
        store = await Store.get(store_id)
        if not store:
            raise HTTPException(422, f"Store {store_id} doesn't exist!")
        await crud.get_store(None, None, store, True)
        if not store.wallets:
            raise HTTPException(422, "No wallet linked")
        if not kwargs.get("user_id"):
            kwargs["user_id"] = store.user_id
        kwargs.pop("products", None)
        return await super().create(**kwargs), store.wallets


class Setting(db.Model):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text)
    value = Column(Text)


class Token(db.Model):
    __tablename__ = "tokens"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"), index=True)
    app_id = Column(String)
    redirect_url = Column(String)
    permissions = Column(ARRAY(String))

    @classmethod
    async def create(cls, **kwargs):
        kwargs["id"] = secrets.token_urlsafe()
        return await super().create(**kwargs)
