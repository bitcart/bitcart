import electrum_bsty
from aiohttp import web
from base import BaseDaemon


class BSTYDaemon(BaseDaemon):
    name = "BSTY"
    electrum = electrum_bsty
    DEFAULT_PORT = 5003


daemon = BSTYDaemon()

app = web.Application()
daemon.configure_app(app)
daemon.start(app)
