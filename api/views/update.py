from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter

from api.services.ext.update import UpdateCheckService

router = APIRouter(route_class=DishkaRoute)


@router.get("/check")
async def check_updates(update_service: FromDishka[UpdateCheckService]) -> dict[str, Any]:
    return await update_service.get_latest_fetched_update()
