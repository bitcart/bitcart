from api import models, schemes


async def get_store(model_id: str, user: schemes.User, item: models.Store, internal: bool = False):
    if internal:
        return item
    elif user:
        return schemes.Store.from_orm(item)
    else:
        return schemes.PublicStore.from_orm(item)
