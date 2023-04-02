import json

import eth

with open("daemons/abi/sep20.json") as f:
    SEP20_ABI = json.loads(f.read())

with open("daemons/tokens/sep20.json") as f:
    SEP20_TOKENS = json.loads(f.read())


class SBCHDaemon(eth.ETHDaemon):
    name = "SBCH"
    DEFAULT_PORT = 5007

    EIP1559_SUPPORTED = False

    ABI = SEP20_ABI
    TOKENS = SEP20_TOKENS


if __name__ == "__main__":
    eth.daemon = SBCHDaemon()
    eth.daemon.start()
