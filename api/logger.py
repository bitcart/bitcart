import copy
import datetime
import logging
import os
from decimal import Decimal
from logging.handlers import TimedRotatingFileHandler

import msgpack
from pydantic import BaseModel


def _shorten_name_of_logrecord(record: logging.LogRecord) -> logging.LogRecord:
    record = copy.copy(record)  # avoid mutating arg
    # strip the main module name from the logger name
    if record.name.startswith("bitcart."):
        record.name = record.name.replace("bitcart.", "", 1)
    return record


def configure_file_logging(logger, file):
    file_handler = TimedRotatingFileHandler(file, when="midnight")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)


class Formatter(logging.Formatter):
    def format(self, record):
        record = _shorten_name_of_logrecord(record)
        return super().format(record)


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


# Env
LOG_FILE = os.environ.get("LOG_FILE")

formatter = Formatter(
    "%(asctime)s - [PID %(process)d] - %(name)s.%(funcName)s [line %(lineno)d] - %(levelname)s - %(message)s"
)

console = logging.StreamHandler()
console.setFormatter(formatter)
console.setLevel(logging.INFO)

logger = logging.getLogger("bitcart.logserver")
logger.setLevel(logging.DEBUG)

logger.addHandler(console)

logger_client = logging.getLogger("bitcart.logclient")
logger_client.setLevel(logging.DEBUG)
socket_handler = MsgpackHandler("localhost", logging.handlers.DEFAULT_TCP_LOGGING_PORT)
socket_handler.setLevel(logging.DEBUG)
logger_client.addHandler(socket_handler)

if LOG_FILE:
    configure_file_logging(logger, LOG_FILE)


def get_logger_server(name):
    return logger.getChild(name.replace("bitcart.logclient.", ""))


def get_logger(name):
    return logger_client.getChild(name.replace("bitcart.logclient.", ""))
