from fastapi import APIRouter

from api import models, schemes, settings, utils
from api.utils.common import prepare_compliant_response

router = APIRouter()


@router.get("/list")
async def get_notifications():
    return prepare_compliant_response(list(settings.settings.notifiers.keys()))


@router.get("/schema")
async def get_notifications_schema():
    return settings.settings.notifiers


crud_routes = utils.routing.ModelView.register(
    router,
    "/",
    models.Notification,
    schemes.UpdateNotification,
    schemes.CreateNotification,
    schemes.DisplayNotification,
    scopes=["notification_management"],
)
