import json
from typing import Any

from aiohttp import ClientSession
from dishka import AsyncContainer, Scope
from outbound_guard import OutboundGuard
from outbound_guard.aiohttp import session as guarded_session

from api.redis import Redis
from api.schemas.policies import Policy
from api.services.settings import SettingService

ALLOWED_HOSTS_KEY = "outbound:allowed_internal_hosts"
ALLOWED_HOSTS_TTL = 300


class OutboundService(OutboundGuard):
    allowed_hosts_key = ALLOWED_HOSTS_KEY

    def __init__(self, container: AsyncContainer, redis_pool: Redis) -> None:
        super().__init__(self.get_allowed_hosts, denial_hint=". Server admins can allow it in allowed_internal_hosts policy")
        self.container = container
        self.redis_pool = redis_pool

    async def get_allowed_hosts(self) -> list[str]:
        if (cached := await self.redis_pool.get(self.allowed_hosts_key)) is not None:
            return json.loads(cached)
        async with self.container(scope=Scope.REQUEST) as container:
            setting_service = await container.get(SettingService)
            hosts = (await setting_service.get_stored_setting(Policy)).allowed_internal_hosts
        await self.redis_pool.set(self.allowed_hosts_key, json.dumps(hosts), ex=ALLOWED_HOSTS_TTL, nx=True)
        return hosts

    async def set_allowed_hosts(self, hosts: list[str]) -> None:
        await self.redis_pool.set(self.allowed_hosts_key, json.dumps(hosts), ex=ALLOWED_HOSTS_TTL)

    def session(self, **kwargs: Any) -> ClientSession:
        return guarded_session(self, **kwargs)
