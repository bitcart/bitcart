from api import models, schemes, utils
from api.db import db


async def store_count():
    return await db.func.count(models.Store.id).gino.scalar()


async def create_store(create_store: schemes.CreateStore, user: schemes.User):
    store = await utils.database.create_object(models.Store, create_store, user)
    if user.is_superuser:
        count = await store_count()
        # First store created by superuser is the one shown on store POS
        # Substract one because current one is already created
        if count - 1 == 0:
            await utils.policies.set_setting(schemes.GlobalStorePolicy(pos_id=store.id))
    return store


async def get_store(model_id: str, user: schemes.User, item: models.Store, internal: bool = False):
    if internal:
        return item
    elif user:
        return schemes.Store.from_orm(item)
    else:
        return schemes.PublicStore.from_orm(item)
