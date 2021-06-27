import electrum_ltc
from aiohttp import web
from base import BaseDaemon


class LTCDaemon(BaseDaemon):
    name = "LTC"
    electrum = electrum_ltc
    DEFAULT_PORT = 5001


if __name__ == "__main__":
    daemon = LTCDaemon()
    app = web.Application()
    daemon.configure_app(app)
    daemon.start(app)
