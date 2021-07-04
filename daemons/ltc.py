from btc import BTCDaemon


class LTCDaemon(BTCDaemon):
    name = "LTC"
    DEFAULT_PORT = 5001

    def load_electrum(self):
        import electrum_ltc

        self.electrum = electrum_ltc


if __name__ == "__main__":
    daemon = LTCDaemon()
    daemon.start()
