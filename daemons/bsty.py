from btc import BTCDaemon


class BSTYDaemon(BTCDaemon):
    name = "BSTY"
    DEFAULT_PORT = 5003

    def load_electrum(self):
        import electrum_bsty

        self.electrum = electrum_bsty


if __name__ == "__main__":
    daemon = BSTYDaemon()
    daemon.start()
