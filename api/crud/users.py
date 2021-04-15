from fastapi import HTTPException

from api import models, schemes, utils
from api.db import db


async def user_count():
    return await db.func.count(models.User.id).gino.scalar()


async def create_user(user: schemes.CreateUser, auth_user: schemes.User):
    register_off = (await utils.policies.get_setting(schemes.Policy)).disable_registration
    if register_off and (not auth_user or not auth_user.is_superuser):
        raise HTTPException(422, "Registration disabled")
    is_superuser = False
    if auth_user is None:
        count = await user_count()
        is_superuser = True if count == 0 else False
    elif auth_user and auth_user.is_superuser:
        is_superuser = user.is_superuser
    d = user.dict()
    d["hashed_password"] = utils.authorization.get_password_hash(d.pop("password", None))
    d["is_superuser"] = is_superuser
    return await models.User.create(**d)


def hash_user(d: dict):
    if "password" in d:
        if d["password"] is not None:
            d["hashed_password"] = utils.authorization.get_password_hash(d["password"])
        del d["password"]
    return d


async def put_user(item: models.User, model: schemes.User, user: schemes.DisplayUser):
    d = hash_user(model.dict())
    await item.update(**d).apply()


async def patch_user(item: models.User, model: schemes.User, user: schemes.DisplayUser):
    d = hash_user(model.dict(exclude_unset=True))
    await item.update(**d).apply()
