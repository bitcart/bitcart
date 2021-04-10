from .. import models, schemes


async def create_notification(notification: schemes.CreateNotification, user: schemes.User):
    return await models.Notification.create(**notification.dict(), user_id=user.id)
