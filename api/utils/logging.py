from contextlib import contextmanager

from api import settings
from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


@contextmanager
def log_errors():  # pragma: no cover
    try:
        yield
    except Exception as e:
        logger.error(get_exception_message(e))


# Used to find all safe-to-delete logs
def log_filter(filename):
    return settings.settings.log_file_regex.match(filename) and filename != settings.settings.log_file_name
