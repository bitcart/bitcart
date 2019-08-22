from typing import Union

from fastapi import BackgroundTasks, HTTPException

from . import models, schemes, tasks, utils
from .db import db


async def user_count():
    return await db.func.count(
        models.User.id
    ).gino.scalar()  # pylint: disable=no-member


async def create_user(user: schemes.CreateUser):
    count = await user_count()
    return await models.User.create(
        username=user.username,
        hashed_password=utils.get_password_hash(user.password),
        email=user.email,
        is_superuser=True if count == 0 else False,
    )


async def create_invoice(
    invoice: schemes.CreateInvoice, background_tasks: BackgroundTasks
):
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
    background_tasks.add_task(tasks.poll_updates, obj, xpub, True)
    return obj


async def invoice_add_related(item: models.Invoice):
    # add related products
    result = (
        await models.ProductxInvoice.select("product_id")
        .where(models.ProductxInvoice.invoice_id == item.id)
        .gino.all()
    )
    item.products = [product_id for product_id, in result]


async def get_invoice(model_id: Union[int, str]):
    item = await models.Invoice.get(model_id)
    if not item:
        raise HTTPException(
            status_code=404, detail=f"Object with id {model_id} does not exist!"
        )
    await invoice_add_related(item)
    return item


async def get_invoices():
    items = await models.Invoice.query.gino.all()
    for i in items:
        await invoice_add_related(i)
    return items
