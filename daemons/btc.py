import electrum
from aiohttp import web
from base import BaseDaemon


class BTCDaemon(BaseDaemon):
    name = "BTC"
    electrum = electrum
    DEFAULT_PORT = 5000


if __name__ == "__main__":
    daemon = BTCDaemon()
    app = web.Application()
    daemon.configure_app(app)
    daemon.start(app)
