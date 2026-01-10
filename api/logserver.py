import contextlib
import logging
import socket
import socketserver
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

import msgpack

from api.constants import LOGSERVER_PORT
from api.logging import configure as configure_logging
from api.logging import get_logger
from api.settings import Settings


class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    def decode_msgpack(self, obj: dict[str, Any]) -> Any:
        result: Any = obj
        if "__datetime__" in obj:
            result = datetime.strptime(obj["data"], "%Y%m%dT%H:%M:%S.%f")
        elif "__decimal__" in obj:
            result = Decimal(obj["data"])
        return result

    def handle(self) -> None:
        unpacker = msgpack.Unpacker(use_list=False, object_hook=self.decode_msgpack, strict_map_key=False)

        while True:
            data = self.connection.recv(1024)
            if not data:
                break
            unpacker.feed(data)
            for obj in unpacker:
                record = logging.makeLogRecord(obj)
                self.handle_log_record(record)

    def handle_log_record(self, record: logging.LogRecord) -> None:
        if isinstance(record.msg, dict):  # happens when structlog is passed to logging, but formatter was not applied
            record.__dict__.update(record.msg)
        record.__dict__.pop("_name", None)  # added by structlog
        logger = get_logger(record.name)
        logger.handle(record)


class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(
        self,
        host: str = "localhost",
        port: int = LOGSERVER_PORT,
        handler: type[LogRecordStreamHandler] = LogRecordStreamHandler,
    ) -> None:
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self) -> None:
        import select

        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()], [], [], self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort


def wait_for_port(host: str = "localhost", port: int = LOGSERVER_PORT, timeout: float = 5.0) -> None:
    start_time = time.perf_counter()
    while True:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                break
        except OSError as ex:
            time.sleep(0.01)
            if time.perf_counter() - start_time >= timeout:
                raise TimeoutError(
                    f"Waited too long for the port {port} on host {host} to start accepting connections."
                ) from ex


def main() -> None:
    settings = Settings(IS_WORKER=True)
    configure_logging(settings=settings, logserver=True)
    tcpserver = LogRecordSocketReceiver(host=settings.logserver_host)
    with contextlib.suppress(KeyboardInterrupt):
        tcpserver.serve_until_stopped()
