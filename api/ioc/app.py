from collections.abc import AsyncIterator

from dishka import Provider, Scope, from_context, provide
from faststream.redis import RedisBroker
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from api.db import AsyncEngine, AsyncSession, AsyncSessionMaker, create_async_engine, create_async_sessionmaker, get_db_session
from api.logfire import instrument_sqlalchemy
from api.plugins import PluginClasses
from api.redis import Redis, create_redis
from api.services.core.password_hasher import PasswordHasher
from api.settings import Settings
from api.templates import TemplateManager
from api.types import PasswordHasherProtocol, TasksBroker


class AppProvider(Provider):
    settings = from_context(provides=Settings, scope=Scope.RUNTIME)
    plugin_classes = from_context(provides=PluginClasses, scope=Scope.RUNTIME)

    @provide(scope=Scope.RUNTIME, provides=TasksBroker)
    async def get_broker(self, settings: Settings) -> AsyncIterator[TasksBroker]:
        async with RedisBroker(url=settings.redis_url) as broker:
            yield broker

    @provide(scope=Scope.APP)
    async def get_async_engine(self, settings: Settings) -> AsyncIterator[AsyncEngine]:
        engine = create_async_engine(settings, "app")
        instrument_sqlalchemy(settings, engine.sync_engine)
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    def get_session_maker(self, async_engine: AsyncEngine) -> AsyncSessionMaker:
        return create_async_sessionmaker(async_engine)

    @provide(scope=Scope.RUNTIME)
    def get_password_context(self) -> PasswordHash:
        return PasswordHash((BcryptHasher(rounds=12),))

    @provide(scope=Scope.RUNTIME)
    def get_template_manager(self) -> TemplateManager:
        return TemplateManager()

    password_hasher = provide(PasswordHasher, scope=Scope.RUNTIME, provides=PasswordHasherProtocol)


provider = AppProvider()
provider.provide(create_redis, provides=Redis, scope=Scope.RUNTIME)
provider.provide(get_db_session, provides=AsyncSession, scope=Scope.SESSION)
