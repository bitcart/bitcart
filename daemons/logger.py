import datetime
import logging
import os
import sys


class OTelExtraStripper(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for attr in ("otelSpanID", "otelTraceID", "otelTraceSampled", "otelServiceName", "levellower"):
            if hasattr(record, attr):
                delattr(record, attr)
        return True


class UTCFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.datetime.fromtimestamp(record.created, tz=datetime.UTC)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

    def format(self, record):
        record.levellower = record.levelname.lower()
        return super().format(record)


def configure_logging(debug: bool = False):
    if not debug:
        logging.disable(logging.CRITICAL)
        return
    logging.disable(logging.NOTSET)
    log_format = "%(asctime)s [%(levellower)s] %(message)s [%(name)s]"
    date_format = "%Y-%m-%d %H:%M:%S.%f %Z"
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = UTCFormatter(log_format, datefmt=date_format)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    if os.getenv("BITCART_OTEL_ENABLED", "false").lower() == "true":
        from opentelemetry._logs import get_logger_provider
        from opentelemetry.sdk._logs import LoggingHandler

        otel_handler = LoggingHandler(level=logging.NOTSET, logger_provider=get_logger_provider())
        otel_handler.addFilter(OTelExtraStripper())
        root_logger.addHandler(otel_handler)
    # turn off loggers which will appear later and not yet loaded
    logging.getLogger("httpcore").setLevel(logging.CRITICAL + 1)
    for logger_name in list(logging.Logger.manager.loggerDict.keys()):
        if not logger_name.startswith("daemons.") and logger_name != "daemons" and not logger_name.startswith("electrum"):
            logging.getLogger(logger_name).disabled = True
            logging.getLogger(logger_name).propagate = False


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("daemons.") and name != "daemons":
        name = f"daemons.{name}"
    return logging.getLogger(name)
