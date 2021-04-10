from typing import Iterable

from .. import models


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
