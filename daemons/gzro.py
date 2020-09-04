import electrum_gzro
from aiohttp import web
from base import BaseDaemon


class GZRODaemon(BaseDaemon):
    name = "GZRO"
    electrum = electrum_gzro
    DEFAULT_PORT = 5002


daemon = GZRODaemon()

app = web.Application()
daemon.configure_app(app)
daemon.start(app)
