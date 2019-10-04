import electrum_gzro
from aiohttp import web

from base import BaseDaemon, rpc


class GZRODaemon(BaseDaemon):
    name = "GZRO"
    electrum = electrum_gzro
    DEFAULT_PORT = 5002


daemon = GZRODaemon()

app = web.Application()
app.router.add_post("/", daemon.handle_request)
app.on_startup.append(daemon.on_startup)
web.run_app(app, host=daemon.HOST, port=daemon.PORT)
