from bch import BCHDaemon


class XRGDaemon(BCHDaemon):
    name = "XRG"
    DEFAULT_PORT = 5005

    def load_electrum(self):
        import oregano

        self.electrum = oregano
        self.NETWORK_MAPPING = {
            "mainnet": self.electrum.networks.set_mainnet,
        }


if __name__ == "__main__":
    daemon = XRGDaemon()
    daemon.start()
