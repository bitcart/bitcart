import socket
from typing import Any

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Security
from starlette.requests import Request

from api import models, utils
from api.constants import AuthScopes
from api.schemas.configurator import ConfiguratorDeploySettings
from api.schemas.misc import SSHSettings
from api.services.ext.configurator import ConfiguratorService

router = APIRouter(route_class=DishkaRoute)


@router.post("/deploy")
async def generate_deployment(
    configurator_service: FromDishka[ConfiguratorService],
    deploy_settings: ConfiguratorDeploySettings,
    request: Request,
) -> Any:
    return await configurator_service.generate_deployment(request, deploy_settings)


@router.get("/deploy-result/{deploy_id}")
async def get_deploy_result(configurator_service: FromDishka[ConfiguratorService], deploy_id: str, request: Request) -> Any:
    return await configurator_service.get_deploy_result(request, deploy_id)


@router.post("/server-settings")
async def get_server_settings(
    configurator_service: FromDishka[ConfiguratorService],
    ssh_settings: SSHSettings | None = None,
    user: models.User | None = Security(utils.authorization.optional_auth_dependency, scopes=[AuthScopes.SERVER_MANAGEMENT]),
) -> Any:
    return await configurator_service.get_server_settings(ssh_settings, user)


@router.get("/dns-resolve")
async def check_dns_entry(name: str) -> Any:
    try:
        socket.getaddrinfo(name, 0)
        return True
    except Exception:
        return False
