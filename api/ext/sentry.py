import sentry_sdk
from sentry_sdk.integrations.logging import ignore_logger

from api.settings import Settings


def configure_sentry(settings: Settings):  # pragma: no cover
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=1.0,
            _experiments={
                "continuous_profiling_auto_start": True,
            },
            add_full_stack=True,
        )
        ignore_logger("paramiko.transport")
        ignore_logger("apprise")
