from contextlib import contextmanager

from api.logger import get_exception_message, get_logger

logger = get_logger(__name__)


@contextmanager
def log_errors():  # pragma: no cover
    try:
        yield
    except Exception as e:
        logger.error(get_exception_message(e))
