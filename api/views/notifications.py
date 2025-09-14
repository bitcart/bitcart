from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from api.constants import AuthScopes
from api.schemas.notifications import CreateNotification, DisplayNotification, UpdateNotification
from api.services.crud.notifications import NotificationService
from api.services.notification_manager import NotificationManager
from api.utils.common import prepare_compliant_response
from api.utils.routing import create_crud_router

router = APIRouter(route_class=DishkaRoute)


@router.get("/list")
async def get_notifications(notification_manager: FromDishka[NotificationManager]) -> Any:
    return prepare_compliant_response(list(notification_manager.notifiers.keys()))


@router.get("/schema")
async def get_notifications_schema(notification_manager: FromDishka[NotificationManager]) -> Any:
    return notification_manager.notifiers


create_crud_router(
    CreateNotification,
    UpdateNotification,
    DisplayNotification,
    NotificationService,
    router=router,
    required_scopes=[AuthScopes.NOTIFICATION_MANAGEMENT],
)
