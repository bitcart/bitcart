from typing import Any

from aiohttp import ClientSession
from dishka import AsyncContainer, Scope
from outbound_guard import OutboundGuard
from outbound_guard.aiohttp import session as guarded_session

from api.schemas.policies import Policy
from api.services.settings import SettingService


class OutboundService(OutboundGuard):
    def __init__(self, container: AsyncContainer) -> None:
        super().__init__(self.get_allowed_hosts, denial_hint=". Server admins can allow it in allowed_internal_hosts policy")
        self.container = container

    async def get_allowed_hosts(self) -> list[str]:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            return (await setting_service.get_stored_setting(Policy)).allowed_internal_hosts

    def session(self, **kwargs: Any) -> ClientSession:
        return guarded_session(self, **kwargs)
