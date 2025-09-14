from dishka import Provider

from api.ioc.app import provider as app_provider
from api.ioc.repositories import RepositoriesProvider
from api.ioc.services import ServicesProvider
from api.ioc.starlette import setup_dishka


def get_providers() -> list[Provider]:
    return [app_provider, ServicesProvider(), RepositoriesProvider()]


__all__ = ["get_providers", "setup_dishka"]
