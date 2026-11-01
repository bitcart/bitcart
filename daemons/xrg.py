from bch import BCHDaemon
from utils import rpc


class XRGDaemon(BCHDaemon):
    name = "XRG"
    DEFAULT_PORT = 5005
    DATA_PATH_OPTION = "oregano_path"

    def load_electrum(self):
        import oregano

        self.electrum = oregano
        self.NETWORK_MAPPING = {
            "mainnet": self.electrum.networks.set_mainnet,
        }
        self.reuse_expired_request_addresses()

    @rpc(requires_wallet=True)
    def addrequest(self, *args, **kwargs):
        wallet = kwargs.pop("wallet", None)
        result = self.wallets[wallet]["cmd"].addrequest(*args, **kwargs)
        return self.format_request(result, wallet)

    @rpc
    def validatecontract(self, address, wallet=None):  # fallback for other coins without smart contracts
        return False

    @rpc
    def get_tokens(self, wallet=None):  # fallback
        return {}


if __name__ == "__main__":
    daemon = XRGDaemon()
    daemon.start()
