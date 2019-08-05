from . import models, schemes
from .db import db


async def user_count():
    return await db.func.count(models.User.id).gino.scalar()


async def create_user(user: schemes.User):
    count = await user_count()
    await models.User.create(
        username=user.username,
        password=user.password,
        email=user.email,
        is_superuser=True if count == 0 else False)
