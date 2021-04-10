from fastapi import APIRouter

from .. import crud, models, schemes, settings, utils

router = APIRouter()


@router.get("/list")
async def get_notifications():
    return {
        "count": len(settings.notifiers),
        "next": None,
        "previous": None,
        "result": list(settings.notifiers.keys()),
    }


@router.get("/schema")
async def get_notifications_schema():
    return settings.notifiers


utils.routing.ModelView.register(
    router,
    "/",
    models.Notification,
    schemes.Notification,
    schemes.CreateNotification,
    custom_methods={"post": crud.notifications.create_notification},
    scopes=["notification_management"],
)
