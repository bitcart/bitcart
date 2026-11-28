from typing import Any

from aiohttp import ClientSession
from dishka import AsyncContainer, Scope
from outbound_guard import OutboundGuard
from outbound_guard.aiohttp import session as guarded_session
from pydantic import TypeAdapter

from api.kit.cache import CachedValue
from api.redis import Redis
from api.schemas.policies import Policy
from api.services.settings import SettingService

ALLOWED_HOSTS_KEY = "outbound:allowed_internal_hosts"
ALLOWED_HOSTS_TTL = 60


class OutboundService(OutboundGuard):
    def __init__(self, container: AsyncContainer, redis_pool: Redis) -> None:
        super().__init__(self.get_allowed_hosts, denial_hint=". Server admins can allow it in allowed_internal_hosts policy")
        self.container = container
        self.allowed_hosts = CachedValue(redis_pool, ALLOWED_HOSTS_KEY, TypeAdapter(list[str]), ALLOWED_HOSTS_TTL)

    async def get_allowed_hosts(self) -> list[str]:
        return await self.allowed_hosts.get(self.load_allowed_hosts)

    async def load_allowed_hosts(self) -> list[str]:
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            return (await setting_service.get_stored_setting(Policy)).allowed_internal_hosts

    async def forget_allowed_hosts(self) -> None:
        await self.allowed_hosts.invalidate()

    def session(self, **kwargs: Any) -> ClientSession:
        return guarded_session(self, **kwargs)
