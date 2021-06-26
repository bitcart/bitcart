import oregano
from aiohttp import web
from bch import BCHDaemon


class XRGDaemon(BCHDaemon):
    name = "XRG"
    electrum = oregano
    DEFAULT_PORT = 5005
    NETWORK_MAPPING = {
        "mainnet": electrum.networks.set_mainnet,
    }


if __name__ == "__main__":
    daemon = XRGDaemon()
    app = web.Application()
    daemon.configure_app(app)
    daemon.start(app)
