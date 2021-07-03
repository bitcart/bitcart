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

    def create_daemon(self):  # TODO: upgrade to support listen_jsonrpc
        return self.electrum.daemon.Daemon(
            self.electrum_config,
            fd=self.electrum.daemon.get_fd_or_server(self.electrum_config)[0],
            is_gui=False,
            plugins=[],
        )


if __name__ == "__main__":
    daemon = XRGDaemon()
    app = web.Application()
    daemon.configure_app(app)
    daemon.start(app)
