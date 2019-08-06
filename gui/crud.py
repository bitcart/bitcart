from . import models, schemes, utils
from .db import db


async def user_count():
    return await db.func.count(models.User.id).gino.scalar()  # pylint: disable=no-member


async def create_user(user: schemes.CreateUser):
    count = await user_count()
    return await models.User.create(
        username=user.username,
        hashed_password=utils.get_password_hash(user.password),
        email=user.email,
        is_superuser=True if count == 0 else False)
