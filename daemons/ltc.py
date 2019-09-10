import electrum_ltc
from aiohttp import web

from base import BaseDaemon, rpc


class LTCDaemon(BaseDaemon):
    name = "LTC"
    electrum = electrum_ltc
    AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction"]
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
    }
    DEFAULT_PORT = 5001

    def _process_events(self, event, *args):
        wallet = None
        data = {}
        if event == "blockchain_updated":
            data["height"] = self.network.get_local_height()
        elif event == "new_transaction":
            wallet, tx = args
            data["tx"] = tx.txid()
        else:
            return None, None
        return data, wallet


daemon = LTCDaemon()

app = web.Application()
app.router.add_post("/", daemon.handle_request)
app.on_startup.append(daemon.on_startup)
web.run_app(app, host=daemon.HOST, port=daemon.PORT)
