import copy
import inspect
import logging
import os
import platform
import sys
from logging.handlers import TimedRotatingFileHandler

from starlette.datastructures import CommaSeparatedStrings

from api.version import GIT_REPO_URL, VERSION, WEBSITE


def _shorten_name_of_logrecord(record: logging.LogRecord) -> logging.LogRecord:
    record = copy.copy(record)  # avoid mutating arg
    # strip the main module name from the logger name
    if record.name.startswith("bitcart."):
        record.name = record.name.replace("bitcart.", "", 1)
    return record


def configure_file_logging(logger, file):  # pragma: no cover
    file_handler = TimedRotatingFileHandler(file, when="midnight")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)


class Formatter(logging.Formatter):
    def format(self, record):
        record = _shorten_name_of_logrecord(record)
        return super().format(record)


def get_class_from_frame(fr):
    args, _, _, value_dict = inspect.getargvalues(fr)
    if len(args) and args[0] == "self":  # pragma: no cover: TODO: remove when we start using logging in classes
        instance = value_dict.get("self", None)
        if instance:
            return getattr(instance, "__class__", None)
    return ""


class ContextFilter(logging.Filter):
    def filter(self, record):
        stack = inspect.stack()[7]
        parsed_class = get_class_from_frame(stack[0])
        record.class_name = f"{parsed_class.__name__}::" if parsed_class else ""
        return True


# Env
LOG_FILE = os.environ.get("LOG_FILE")
DOCKER_ENV = os.environ.get("IN_DOCKER", False)
ENABLED_CRYPTOS = CommaSeparatedStrings(os.environ.get("BITCART_CRYPTOS", "btc"))


formatter = Formatter(
    "%(asctime)s - [PID %(process)d] - %(name)s.%(class_name)s%(funcName)s [line %(lineno)d] - %(levelname)s - %(message)s"
)

context_filter = ContextFilter()

console = logging.StreamHandler()
console.setFormatter(formatter)
console.addFilter(context_filter)
console.setLevel(logging.INFO)

logger = logging.getLogger("bitcart")
logger.setLevel(logging.DEBUG)

logger.addHandler(console)


if LOG_FILE:  # pragma: no cover
    configure_file_logging(logger, LOG_FILE)


def get_logger(name):
    return logger.getChild(name.replace("bitcart.", ""))


def log_startup_info(logger):  # pragma: no cover: production only
    logger.info(f"BitcartCC version: {VERSION} - {WEBSITE} - {GIT_REPO_URL}")
    logger.info(f"Python version: {sys.version}. On platform: {platform.platform()}")
    logger.info(
        f"BITCART_CRYPTOS={','.join([item for item in ENABLED_CRYPTOS])}; IN_DOCKER={DOCKER_ENV}; " f"LOG_FILE={LOG_FILE}"
    )
