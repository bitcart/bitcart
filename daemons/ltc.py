import electrum_ltc
from aiohttp import web
from base import BaseDaemon


class LTCDaemon(BaseDaemon):
    name = "LTC"
    electrum = electrum_ltc
    DEFAULT_PORT = 5001


daemon = LTCDaemon()

app = web.Application()
app.router.add_post("/", daemon.handle_request)
app.on_startup.append(daemon.on_startup)
app.on_shutdown.append(daemon.on_shutdown)
web.run_app(app, host=daemon.HOST, port=daemon.PORT)
