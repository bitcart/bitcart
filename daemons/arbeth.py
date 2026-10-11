import json

import eth

with open("daemons/tokens/erc20arbitrum.json") as f:
    ERC20_TOKENS = json.loads(f.read())


class ARBETHDaemon(eth.ETHDaemon):
    name = "ARBETH"
    DEFAULT_PORT = 5012

    DEFAULT_MAX_SYNC_BLOCKS = 3600  # (60/0.25)=240*15 (a block every ~0.25 seconds, keep up to 15 minutes of data)

    TOKENS = ERC20_TOKENS


if __name__ == "__main__":
    daemon = ARBETHDaemon()
    daemon.start()
