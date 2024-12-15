from fastapi import APIRouter, Security

from api import models, utils
from api.ext import tor as tor_ext
from api.plugins import apply_filters

router = APIRouter()


@router.get("/services")
async def get_services(
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=["server_management"])
):
    key = "services_dict" if user else "anonymous_services_dict"
    async with utils.redis.wait_for_redis():
        return await apply_filters("tor_services", await tor_ext.get_data(key, {}, json_decode=True))
