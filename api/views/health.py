from collections.abc import Awaitable
from typing import Any, cast

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.db import AsyncEngine
from api.redis import Redis
from api.services.coins import CoinService

router = APIRouter(route_class=DishkaRoute)


@router.get("/live", response_model=dict)
async def live() -> Any:
    return {"status": "ok"}


@router.get("/ready", response_model=dict)
async def ready(db: FromDishka[AsyncEngine], redis: FromDishka[Redis], coin_service: FromDishka[CoinService]) -> Any:
    try:
        async with db.connect() as connection:
            (await connection.execute(text("SELECT 1"))).scalar_one()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "detail": "database unreachable"},
        )
    try:
        await cast(Awaitable[bool], redis.ping())
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "detail": "redis unreachable"},
        )
    coins_health = await coin_service.coins_healthcheck()
    failed_coins = [coin for coin, status in coins_health.items() if status != "ok"]
    if failed_coins:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "detail": f"coins unreachable: {', '.join(failed_coins)}",
            },
        )
    return {"status": "ok"}
