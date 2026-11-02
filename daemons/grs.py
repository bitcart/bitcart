from btc import BTCDaemon


class GRSDaemon(BTCDaemon):
    name = "GRS"
    DEFAULT_PORT = 5010
    UNSUPPORTED_NETWORKS = ("testnet4", "mutinynet")

    def load_electrum(self):
        import electrum_grs

        self.electrum = electrum_grs


if __name__ == "__main__":
    daemon = GRSDaemon()
    daemon.start()
