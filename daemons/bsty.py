import electrum_bsty
from aiohttp import web
from base import BaseDaemon


class BSTYDaemon(BaseDaemon):
    name = "BSTY"
    electrum = electrum_bsty
    DEFAULT_PORT = 5003


daemon = BSTYDaemon()

app = web.Application()
app.router.add_post("/", daemon.handle_request)
app.on_startup.append(daemon.on_startup)
app.on_shutdown.append(daemon.on_shutdown)
web.run_app(app, host=daemon.HOST, port=daemon.PORT)
