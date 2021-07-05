from btc import BTCDaemon
from utils import rpc


class GZRODaemon(BTCDaemon):
    name = "GZRO"
    DEFAULT_PORT = 5002

    def load_electrum(self):
        import electrum_gzro

        self.electrum = electrum_gzro

    @rpc
    def recommended_fee(self, target, wallet=None) -> float:  # no fee estimation for GZRO
        return 0


if __name__ == "__main__":
    daemon = GZRODaemon()
    daemon.start()
