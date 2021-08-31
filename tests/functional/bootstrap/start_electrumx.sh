#!/usr/bin/env bash
# thanks to electrum for regtest testing setup scripts
set -eux pipefail
cd
rm -rf ~/.electrumx_db
mkdir ~/.electrumx_db
COST_SOFT_LIMIT=0 COST_HARD_LIMIT=0 COIN=BitcoinSegwit SERVICES=tcp://:51001 NET=regtest DAEMON_URL=http://doggman:donkey@127.0.0.1:18554 DB_DIRECTORY=~/.electrumx_db electrumx_server
