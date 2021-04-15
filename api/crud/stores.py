from typing import Iterable

from api import models, pagination, schemes


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
    await models.NotificationxStore.delete.where(models.NotificationxStore.store_id == item.id).gino.status()
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
    obj.checkout_settings = schemes.StoreCheckoutSettings()
    return obj


async def store_add_related(item: models.Store):
    # add related wallets
    if not item:
        return
    item.checkout_settings = item.get_setting(schemes.StoreCheckoutSettings)
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
