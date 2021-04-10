from fastapi import APIRouter, HTTPException
from fastapi.security import SecurityScopes
from starlette.requests import Request

from .. import utils
from ..ext import tor as tor_ext

router = APIRouter()


@router.get("/services")
async def get_services(request: Request):
    try:
        user = await utils.authorization.AuthDependency()(request, SecurityScopes(["server_management"]))
    except HTTPException:
        user = None
    key = "services_dict" if user else "anonymous_services_dict"
    async with utils.redis.wait_for_redis():
        return await tor_ext.get_data(key, {}, json_decode=True)
