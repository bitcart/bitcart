#!/usr/bin/env bash
# thanks to electrum for regtest testing setup scripts

set -eux pipefail
export HOME=~
mkdir -p ~/.bitcoin-cash-node
cat >~/.bitcoin-cash-node/bitcoin.conf <<EOF
regtest=1
txindex=1
printtoconsole=1
rpcuser=doggman
rpcpassword=donkey
rpcallowip=127.0.0.1
zmqpubrawblock=tcp://127.0.0.1:28332
zmqpubrawtx=tcp://127.0.0.1:28333
fallbackfee=0.0002
[regtest]
rpcbind=0.0.0.0
rpcport=18554
EOF
rm -rf ~/.bitcoin-cash-node/regtest
screen -S bitcoin-cash-node -X quit || true
screen -S bitcoin-cash-node -m -d /opt/bitcoin-cash-node/bin/bitcoind -datadir=$HOME/.bitcoin-cash-node -regtest
sleep 6
/opt/bitcoin-cash-node/bin/bitcoin-cli createwallet test_wallet
addr=$(/opt/bitcoin-cash-node/bin/bitcoin-cli -rpcwallet=test_wallet getnewaddress)
/opt/bitcoin-cash-node/bin/bitcoin-cli -rpcwallet=test_wallet generatetoaddress 150 $addr >/dev/null
screen -r bitcoin-cash-node
