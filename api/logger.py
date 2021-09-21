import datetime
import logging
import re
import traceback
from decimal import Decimal
from logging.handlers import TimedRotatingFileHandler

import msgpack
from pydantic import BaseModel

from api.constants import LOGSERVER_PORT
from api.settings import LOG_FILE, LOGSERVER_HOST


def get_exception_message(exc: Exception):
    return "\n" + "".join(traceback.format_exception(etype=type(exc), value=exc, tb=exc.__traceback__))


def timed_log_namer(default_name):
    base_filename, *ext, date = default_name.split(".")
    return f"{base_filename}{date}.{'.'.join(ext)}"  # i.e. "bitcart12345678.log"


def configure_file_logging():
    if LOG_FILE:
        handler = TimedRotatingFileHandler(LOG_FILE, when="midnight")
        handler.suffix = "%Y%m%d"
        handler.extMatch = re.compile(r"^\d{8}(\.\w+)?$")
        handler.namer = timed_log_namer
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)


class MsgpackHandler(logging.handlers.SocketHandler):
    def __init__(self, host, port):
        logging.handlers.SocketHandler.__init__(self, host, port)

    def msgpack_encoder(self, obj):
        if isinstance(obj, BaseModel):
            return obj.dict()
        if isinstance(obj, datetime.datetime):
            return {"__datetime__": True, "data": obj.strftime("%Y%m%dT%H:%M:%S.%f")}
        if isinstance(obj, Decimal):
            return {"__decimal__": True, "data": str(obj)}
        return obj

    def makePickle(self, record):
        return msgpack.packb(record.__dict__, default=self.msgpack_encoder)


formatter = logging.Formatter(
    "%(asctime)s - [PID %(process)d] - %(name)s.%(funcName)s [line %(lineno)d] - %(levelname)s - %(message)s"
)

console = logging.StreamHandler()
console.setFormatter(formatter)
console.setLevel(logging.INFO)

logger = logging.getLogger("api.logserver")
logger.setLevel(logging.DEBUG)

logger.addHandler(console)

logger_client = logging.getLogger("api.logclient")
bitcart_logger = logging.getLogger("bitcart")
logger_client.setLevel(logging.DEBUG)
bitcart_logger.setLevel(logging.DEBUG)

socket_handler = MsgpackHandler(LOGSERVER_HOST, LOGSERVER_PORT)
socket_handler.setLevel(logging.DEBUG)
logger_client.addHandler(socket_handler)
bitcart_logger.addHandler(socket_handler)


def get_logger_server(name):
    return logger.getChild(name)


def get_logger(name):
    return logger_client.getChild(name.replace("api.logclient.", ""))
