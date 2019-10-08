import electrum
from aiohttp import web

from base import BaseDaemon, rpc


class BTCDaemon(BaseDaemon):
    name = "BTC"
    electrum = electrum
    DEFAULT_PORT = 5000


daemon = BTCDaemon()

app = web.Application()
app.router.add_post("/", daemon.handle_request)
app.on_startup.append(daemon.on_startup)
app.on_shutdown.append(daemon.on_shutdown)
web.run_app(app, host=daemon.HOST, port=daemon.PORT)
