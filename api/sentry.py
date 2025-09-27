import os

import sentry_sdk
from sentry_sdk.integrations.logging import ignore_logger

from api.settings import Settings


def configure_sentry(settings: Settings) -> None:
    if not settings.SENTRY_DSN or not settings.is_production():
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        release=os.environ.get("RELEASE_VERSION", "development"),
        environment=settings.ENV,
        _experiments={
            "continuous_profiling_auto_start": True,
        },
    )
    ignore_logger("paramiko.transport")
    ignore_logger("apprise")
