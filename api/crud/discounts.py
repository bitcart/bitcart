from .. import models, schemes


async def create_discount(discount: schemes.CreateDiscount, user: schemes.User):
    return await models.Discount.create(**discount.dict(), user_id=user.id)
