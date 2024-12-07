import json

import eth

with open("daemons/tokens/erc20matic.json") as f:
    ERC20_TOKENS = json.loads(f.read())


class MATICDaemon(eth.ETHDaemon):
    name = "MATIC"
    DEFAULT_PORT = 5008

    DEFAULT_MAX_SYNC_BLOCKS = 450  # (60/2)=30*60 (a block every 2 seconds, keep up to 15 minutes of data)

    TOKENS = ERC20_TOKENS


if __name__ == "__main__":
    daemon = MATICDaemon()
    daemon.start()
