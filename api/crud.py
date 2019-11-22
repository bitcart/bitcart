# pylint: disable=no-member
from typing import Iterable

from . import models, pagination, schemes, settings, tasks, utils
from .db import db


async def user_count():
    return await db.func.count(models.User.id).gino.scalar()


async def create_user(user: schemes.CreateUser, auth_user: schemes.User):
    is_superuser = False
    if auth_user is None:
        count = await user_count()
        is_superuser = True if count == 0 else False
    elif auth_user and auth_user.is_superuser:
        is_superuser = user.is_superuser
    return await models.User.create(
        username=user.username,
        hashed_password=utils.get_password_hash(user.password),
        email=user.email,
        is_superuser=is_superuser,
    )


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
    d = hash_user(model.dict(skip_defaults=True))
    await item.update(**d).apply()


async def create_wallet(wallet: schemes.CreateWallet, user: schemes.User):
    return await models.Wallet.create(**wallet.dict(), user_id=user.id)


async def create_invoice(invoice: schemes.CreateInvoice, user: schemes.User):
    d = invoice.dict()
    products = d.get("products")
    obj, xpub = await models.Invoice.create(**d)
    created = []
    for i in products:  # type: ignore
        created.append(
            (
                await models.ProductxInvoice.create(invoice_id=obj.id, product_id=i)
            ).product_id
        )
    obj.products = created
    tasks.poll_updates.send(obj.id, xpub, settings.TEST)
    return obj


async def invoice_add_related(item: models.Invoice):
    # add related products
    if not item:
        return
    result = (
        await models.ProductxInvoice.select("product_id")
        .where(models.ProductxInvoice.invoice_id == item.id)
        .gino.all()
    )
    item.products = [product_id for product_id, in result if product_id]


async def invoices_add_related(items: Iterable[models.Invoice]):
    for item in items:
        await invoice_add_related(item)
    return items


async def get_invoice(model_id: int, user: schemes.User, item: models.Invoice):
    await invoice_add_related(item)
    return item


async def get_invoices(
    pagination: pagination.Pagination, user: schemes.User, data_source
):
    return await pagination.paginate(
        models.Invoice, data_source, user.id, postprocess=invoices_add_related
    )


async def delete_invoice(item: schemes.Invoice, user: schemes.User):
    await models.ProductxInvoice.delete.where(
        models.ProductxInvoice.invoice_id == item.id
    ).gino.status()
    await item.delete()
    return item
