import socket
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.security import SecurityScopes
from starlette.requests import Request

from api import schemes, settings, utils
from api.ext import configurator
from api.ext import ssh as ssh_ext
from api.plugins import run_hook

router = APIRouter()


@router.post("/deploy")
async def generate_deployment(deploy_settings: schemes.ConfiguratorDeploySettings, request: Request):
    this_machine = deploy_settings.mode == "Current"
    scopes = ["server_management"] if this_machine else []
    await configurator.authenticate_request(request, scopes=scopes)
    script = configurator.create_bash_script(deploy_settings)
    ssh_settings = (
        settings.settings.ssh_settings if this_machine else schemes.SSHSettings(**deploy_settings.ssh_settings.dict())
    )
    return await configurator.create_new_task(script, ssh_settings, deploy_settings.mode == "Manual")


@router.get("/deploy-result/{deploy_id}")
async def get_deploy_result(deploy_id: str, request: Request):
    await configurator.authenticate_request(request)
    data = await configurator.get_task(deploy_id)
    if not data:
        raise HTTPException(404, f"Deployment result {deploy_id} does not exist!")
    return data


@router.post("/server-settings")
async def get_server_settings(request: Request, ssh_settings: Optional[schemes.SSHSettings] = None):
    if not ssh_settings:
        await utils.authorization.AuthDependency()(request, SecurityScopes(["server_management"]))
        ssh_settings = settings.settings.ssh_settings
    server_settings = ssh_ext.collect_server_settings(ssh_settings)
    await run_hook("configurator_server_settings", server_settings)
    return server_settings


@router.get("/dns-resolve")
async def check_dns_entry(name: str):
    try:
        socket.getaddrinfo(name, 0)
        return True
    except Exception:
        return False
