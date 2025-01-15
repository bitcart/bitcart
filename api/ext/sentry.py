import sentry_sdk
from sentry_sdk.integrations.logging import ignore_logger

from api.settings import Settings


def configure_sentry(settings: Settings):
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=1.0,
            _experiments={
                "continuous_profiling_auto_start": True,
            },
        )
        ignore_logger("paramiko.transport")
