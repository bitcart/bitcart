from fastapi import APIRouter, HTTPException
from fastapi.security import SecurityScopes
from starlette.requests import Request

from api import utils
from api.ext import tor as tor_ext
from api.plugins import apply_filters

router = APIRouter()


@router.get("/services")
async def get_services(request: Request):
    try:
        user = await utils.authorization.AuthDependency()(request, SecurityScopes(["server_management"]))
    except HTTPException:
        user = None
    key = "services_dict" if user else "anonymous_services_dict"
    async with utils.redis.wait_for_redis():
        return await apply_filters("tor_services", await tor_ext.get_data(key, {}, json_decode=True))
