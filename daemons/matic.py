import json

import eth

with open("daemons/tokens/erc20matic.json") as f:
    ERC20_TOKENS = json.loads(f.read())


class MATICDaemon(eth.ETHDaemon):
    name = "MATIC"
    DEFAULT_PORT = 5008

    DEFAULT_MAX_SYNC_BLOCKS = 1800  # (60/2)=30*60 (a block every 2 seconds, max normal expiry time 60 minutes)
    FIAT_NAME = "matic-network"
    CONTRACT_FIAT_NAME = "polygon-pos"

    TOKENS = ERC20_TOKENS


if __name__ == "__main__":
    eth.daemon = MATICDaemon()
    eth.daemon.start()
