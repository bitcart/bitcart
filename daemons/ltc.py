import electrum_ltc
from aiohttp import web

from base import BaseDaemon, rpc


class LTCDaemon(BaseDaemon):
    name = "LTC"
    electrum = electrum_ltc
    NEW_ELECTRUM = False
    AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction"]
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
    }
    DEFAULT_PORT = 5001

    def create_commands(self, config):
        return self.electrum.commands.Commands(
            config=config, network=self.network, wallet=None
        )

    async def restore_wallet(self, command_runner, xpub, config):
        await command_runner.restore(xpub)

    def load_cmd_wallet(self, cmd, wallet, wallet_path):
        cmd.wallet = wallet

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
