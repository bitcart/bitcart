from fastapi import APIRouter

from api import settings, utils
from api.ext import update as update_ext

router = APIRouter()


@router.get("/check")
async def check_updates():
    async with utils.redis.wait_for_redis():
        new_update_tag = await settings.redis_pool.hget(update_ext.REDIS_KEY, "new_update_tag")
        return {"update_available": bool(new_update_tag), "tag": new_update_tag}
