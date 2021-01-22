import electrum_gzro
from aiohttp import web
from base import BaseDaemon, rpc


class GZRODaemon(BaseDaemon):
    name = "GZRO"
    electrum = electrum_gzro
    DEFAULT_PORT = 5002

    @rpc
    def recommended_fee(self, target, wallet=None) -> float:  # no fee estimation for GZRO
        return 0


daemon = GZRODaemon()

app = web.Application()
daemon.configure_app(app)
daemon.start(app)
