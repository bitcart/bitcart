import datetime
import logging
import logging.handlers
import socket
import socketserver
import time
from decimal import Decimal

import msgpack

from .logger import configure_file_logging
from .logger import get_logger_server as get_logger


class LogRecordStreamHandler(socketserver.StreamRequestHandler):
    def decode_msgpack(self, obj):
        if "__datetime__" in obj:
            obj = datetime.datetime.strptime(obj["data"], "%Y%m%dT%H:%M:%S.%f")
        elif "__decimal__" in obj:
            obj = Decimal(obj["data"])
        return obj

    def handle(self):
        unpacker = msgpack.Unpacker(use_list=False, object_hook=self.decode_msgpack)

        while True:
            data = self.connection.recv(1024)
            if not data:
                break
            unpacker.feed(data)
            for obj in unpacker:
                record = logging.makeLogRecord(obj)
                self.handle_log_record(record)

    def handle_log_record(self, record):
        record.name = record.name.replace("bitcart.logclient.", "")
        logger = get_logger(record.name)
        logger.handle(record)


class LogRecordSocketReceiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, host="localhost", port=logging.handlers.DEFAULT_TCP_LOGGING_PORT, handler=LogRecordStreamHandler):
        socketserver.ThreadingTCPServer.__init__(self, (host, port), handler)
        self.abort = 0
        self.timeout = 1
        self.logname = None

    def serve_until_stopped(self):
        import select

        abort = 0
        while not abort:
            rd, wr, ex = select.select([self.socket.fileno()], [], [], self.timeout)
            if rd:
                self.handle_request()
            abort = self.abort


def wait_for_port(host="localhost", port=logging.handlers.DEFAULT_TCP_LOGGING_PORT, timeout=5.0):
    start_time = time.perf_counter()
    while True:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                break
        except OSError as ex:
            time.sleep(0.01)
            if time.perf_counter() - start_time >= timeout:
                raise TimeoutError(
                    "Waited too long for the port {} on host {} to start accepting " "connections.".format(port, host)
                ) from ex


def main():
    configure_file_logging()
    tcpserver = LogRecordSocketReceiver()
    tcpserver.serve_until_stopped()


if __name__ == "__main__":
    main()
