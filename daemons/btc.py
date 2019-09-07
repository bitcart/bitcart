from aiohttp import web
from electrum.transaction import Transaction

from base import BaseDaemon, rpc


class BTCDaemon(BaseDaemon):
    name = "BTC"
    AVAILABLE_EVENTS = ["blockchain_updated", "new_transaction"]
    EVENT_MAPPING = {
        "blockchain_updated": "new_block",
        "new_transaction": "new_transaction",
    }

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

    @rpc
    async def get_transaction(self, tx, wallet=None):
        result = await self.network.interface.session.send_request(
            "blockchain.transaction.get", [tx, True]
        )
        result_formatted = Transaction(result).deserialize()
        result_formatted.update({"confirmations": result.get("confirmations", 0)})
        return result_formatted

    @rpc
    def exchange_rate(self, currency=None, wallet=None) -> str:
        if currency is None:
            currency = self.DEFAULT_CURRENCY
        if self.fx.get_currency() != currency:
            self.fx.set_currency(currency)
        return str(self.fx.exchange_rate())

    @rpc
    def list_currencies(self, wallet=None) -> list:
        return self.fx.get_currencies(True)

    @rpc
    def get_tx_size(self, raw_tx: dict, wallet=None) -> int:
        return Transaction(raw_tx).estimated_size()


daemon = BTCDaemon()

app = web.Application()
app.router.add_post("/", daemon.handle_request)
app.on_startup.append(daemon.on_startup)
web.run_app(app, host=daemon.HOST, port=daemon.PORT)
