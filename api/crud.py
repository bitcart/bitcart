import math
from datetime import timedelta
from decimal import Decimal
from operator import attrgetter
from typing import Iterable

from fastapi import HTTPException
from starlette.datastructures import CommaSeparatedStrings

from . import models, pagination, schemes, settings, tasks, utils
from .db import db


async def user_count():
    return await db.func.count(models.User.id).gino.scalar()


async def create_user(user: schemes.CreateUser, auth_user: schemes.User):
    register_off = (await utils.get_setting(schemes.Policy)).disable_registration
    if register_off and (not auth_user or not auth_user.is_superuser):
        raise HTTPException(422, "Registration disabled")
    is_superuser = False
    if auth_user is None:
        count = await user_count()
        is_superuser = True if count == 0 else False
    elif auth_user and auth_user.is_superuser:
        is_superuser = user.is_superuser
    d = user.dict()
    d["hashed_password"] = utils.get_password_hash(d.pop("password", None))
    d["is_superuser"] = is_superuser
    return await models.User.create(**d)


def hash_user(d: dict):
    if "password" in d:
        if d["password"] is not None:
            d["hashed_password"] = utils.get_password_hash(d["password"])
        del d["password"]
    return d


async def put_user(item: models.User, model: schemes.User, user: schemes.DisplayUser):
    d = hash_user(model.dict())
    await item.update(**d).apply()


async def patch_user(item: models.User, model: schemes.User, user: schemes.DisplayUser):
    d = hash_user(model.dict(exclude_unset=True))
    await item.update(**d).apply()


async def create_wallet(wallet: schemes.CreateWallet, user: schemes.User):
    return await models.Wallet.create(**wallet.dict(), user_id=user.id)


async def create_invoice(invoice: schemes.CreateInvoice, user: schemes.User):
    d = invoice.dict()
    store = await models.Store.get(d["store_id"])
    if not store:
        raise HTTPException(422, f"Store {d['store_id']} doesn't exist!")
    d["currency"] = d["currency"] or store.default_currency or "USD"
    d["expiration"] = store.expiration
    products = d.get("products", {})
    if isinstance(products, list):
        products = {k: 1 for k in products}
    promocode = d.get("promocode")
    d["products"] = list(products.keys())
    obj, wallets = await models.Invoice.create(**d)
    product = None
    if d["products"]:
        product = await models.Product.get(d["products"][0])
        await product_add_related(product)
    created = []
    for key, value in products.items():  # type: ignore
        created.append((await models.ProductxInvoice.create(invoice_id=obj.id, product_id=key, count=value)).product_id)
    obj.products = created
    obj.payments = {}
    task_wallets = {}
    current_date = utils.now()
    discounts = []
    if product:
        discounts = [await models.Discount.get(discount_id) for discount_id in product.discounts]
    discounts = list(filter(lambda x: current_date <= x.end_date, discounts))
    await update_invoice_payments(obj, wallets, discounts, task_wallets, store, product, promocode)
    return obj


async def update_invoice_payments(invoice, wallets, discounts, task_wallets, store, product, promocode):
    for wallet_id in wallets:
        wallet = await models.Wallet.get(wallet_id)
        if wallet.currency not in invoice.payments:
            coin = settings.get_coin(wallet.currency, wallet.xpub)
            discount_id = None
            price = invoice.price / await coin.rate(invoice.currency, accurate=True)
            if math.isnan(price):
                price = invoice.price / await coin.rate(store.default_currency, accurate=True)
            if math.isnan(price):
                price = invoice.price / await coin.rate("USD", accurate=True)
            if math.isnan(price):
                price = invoice.price
            if discounts:
                try:
                    discount = max(
                        filter(
                            lambda x: (not x.currencies or wallet.currency in CommaSeparatedStrings(x.currencies))
                            and (promocode == x.promocode or not x.promocode),
                            discounts,
                        ),
                        key=attrgetter("percent"),
                    )
                    discount_id = discount.id
                    price -= price * (Decimal(discount.percent) / Decimal(100))
                except ValueError:  # no matched discounts
                    pass
            task_wallets[wallet.currency] = wallet.xpub
            data_got = await coin.addrequest(
                str(price), description=product.name if product else "", expire=invoice.expiration
            )
            await models.PaymentMethod.create(
                invoice_id=invoice.id,
                amount=price,
                discount=discount_id,
                currency=wallet.currency,
                payment_address=data_got["address"],
                payment_url=data_got["URI"],
            )
            invoice.payments[wallet.currency] = {
                "payment_address": data_got["address"],
                "payment_url": data_got["URI"],
                "amount": price,
                "discount": discount_id,
                "currency": wallet.currency,
            }
    add_invoice_expiration(invoice)
    tasks.poll_updates.send(invoice.id, task_wallets)


def add_invoice_expiration(obj):
    obj.expiration_seconds = obj.expiration * 60
    date = obj.created + timedelta(seconds=obj.expiration_seconds) - utils.now()
    obj.time_left = utils.time_diff(date)


async def invoice_add_related(item: models.Invoice):
    # add related products
    if not item:
        return
    result = await models.ProductxInvoice.select("product_id").where(models.ProductxInvoice.invoice_id == item.id).gino.all()
    item.products = [product_id for product_id, in result if product_id]
    item.payments = {}
    payment_methods = await models.PaymentMethod.query.where(models.PaymentMethod.invoice_id == item.id).gino.all()
    for method in payment_methods:
        if method.currency not in item.payments:
            item.payments[method.currency] = {
                "payment_address": method.payment_address,
                "payment_url": method.payment_url,
                "amount": method.amount,
                "discount": method.discount,
                "currency": method.currency,
            }
    add_invoice_expiration(item)


async def invoices_add_related(items: Iterable[models.Invoice]):
    for item in items:
        await invoice_add_related(item)
    return items


async def get_invoice(model_id: int, user: schemes.User, item: models.Invoice, internal: bool = False):
    await invoice_add_related(item)
    return item


async def get_invoices(pagination: pagination.Pagination, user: schemes.User):
    return await pagination.paginate(models.Invoice, user.id, postprocess=invoices_add_related)


async def get_store(model_id: int, user: schemes.User, item: models.Store, internal=False):
    if item is None:
        item = await models.Store.get(model_id)  # Extra query to fetch public data
        if item is None:
            return
        user = None  # reset User to display only public data
    await store_add_related(item)
    if internal:
        return item
    elif user:
        return schemes.Store.from_orm(item)
    else:
        return schemes.PublicStore.from_orm(item)


async def get_stores(pagination: pagination.Pagination, user: schemes.User):
    return await pagination.paginate(models.Store, user.id, postprocess=stores_add_related)


async def delete_store(item: schemes.Store, user: schemes.User):
    await models.WalletxStore.delete.where(models.WalletxStore.store_id == item.id).gino.status()
    await item.delete()
    return item


async def create_store(store: schemes.CreateStore, user: schemes.User):
    d = store.dict()
    wallets = d.get("wallets", [])
    notifications = d.get("notifications", [])
    obj = await models.Store.create(**d, user_id=user.id)
    created_wallets = []
    for i in wallets:  # type: ignore
        created_wallets.append((await models.WalletxStore.create(store_id=obj.id, wallet_id=i)).wallet_id)
    obj.wallets = created_wallets
    created_notifications = []
    for i in notifications:  # type: ignore
        created_notifications.append(
            (await models.NotificationxStore.create(store_id=obj.id, notification_id=i)).notification_id
        )
    obj.notifications = created_notifications
    return obj


async def store_add_related(item: models.Store):
    # add related wallets
    if not item:
        return
    result = await models.WalletxStore.select("wallet_id").where(models.WalletxStore.store_id == item.id).gino.all()
    result2 = (
        await models.NotificationxStore.select("notification_id")
        .where(models.NotificationxStore.store_id == item.id)
        .gino.all()
    )
    item.wallets = [wallet_id for wallet_id, in result if wallet_id]
    item.notifications = [notification_id for notification_id, in result2 if notification_id]


async def stores_add_related(items: Iterable[models.Store]):
    for item in items:
        await store_add_related(item)
    return items


async def delete_invoice(item: schemes.Invoice, user: schemes.User):
    await models.ProductxInvoice.delete.where(models.ProductxInvoice.invoice_id == item.id).gino.status()
    await item.delete()
    return item


async def product_add_related(item: models.Product):
    # add related discounts
    if not item:
        return
    result = (
        await models.DiscountxProduct.select("discount_id").where(models.DiscountxProduct.product_id == item.id).gino.all()
    )
    item.discounts = [discount_id for discount_id, in result if discount_id]


async def products_add_related(items: Iterable[models.Product]):
    for item in items:
        await product_add_related(item)
    return items


async def create_discount(discount: schemes.CreateDiscount, user: schemes.User):
    return await models.Discount.create(**discount.dict(), user_id=user.id)


async def create_notification(notification: schemes.CreateNotification, user: schemes.User):
    return await models.Notification.create(**notification.dict(), user_id=user.id)


async def create_template(template: schemes.CreateTemplate, user: schemes.User):
    return await models.Template.create(**template.dict(), user_id=user.id)


def mark_invoice_invalid(orm_model):
    return orm_model.update.values({"status": "invalid"})
