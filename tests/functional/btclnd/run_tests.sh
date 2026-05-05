#!/usr/bin/env bash
# All-in-one script to run BTCLND API flow functional tests.
# Handles: DB reset, API start, worker start, regtest env, daemon, tests, cleanup.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_DIR"

export BITCART_CRYPTOS=btclnd
export BTCLND_NETWORK=regtest
export BTCLND_TOR=false
export PYTHONPATH=daemons

# Use a separate test database — never touch the main 'bitcart' database
TEST_DB_NAME="bitcart_btclnd_test"
export DB_DATABASE="$TEST_DB_NAME"

echo "=== BTCLND Functional Test Runner ==="

cleanup() {
    echo "Cleaning up..."
    kill $(lsof -ti :8000) 2>/dev/null || true
    pkill -f "worker.py" 2>/dev/null || true
    kill $(lsof -ti :5012) 2>/dev/null || true
    pkill -f "lnd.*regtest.*btclnd" 2>/dev/null || true
    bash tests/functional/btclnd/bootstrap.sh stop 2>/dev/null || true
    # Clean up test database (never touches production 'bitcart' database)
    sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$TEST_DB_NAME' AND pid != pg_backend_pid();" 2>/dev/null || true
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS $TEST_DB_NAME;" 2>/dev/null || true
}
trap cleanup EXIT

# 1. Start regtest environment (bitcoind + 2 LND nodes)
echo ">>> Starting regtest environment..."
rm -rf .regtest
bash tests/functional/btclnd/bootstrap.sh start

# 2. Reset test database (separate from production 'bitcart' database)
echo ">>> Resetting test database ($TEST_DB_NAME)..."
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$TEST_DB_NAME' AND pid != pg_backend_pid();" 2>/dev/null || true
sudo -u postgres psql -c "DROP DATABASE IF EXISTS $TEST_DB_NAME;" 2>/dev/null
sudo -u postgres psql -c "CREATE DATABASE $TEST_DB_NAME;" 2>/dev/null
.venv/bin/alembic upgrade head 2>&1 | tail -1

# 3. Start BTCLND daemon
echo ">>> Starting BTCLND daemon..."
BTCLND_DATA_PATH="$PROJECT_DIR/.regtest/daemon" \
BTCLND_NEUTRINO_PEERS="127.0.0.1:18444" \
BTCLND_DEBUG=true \
.venv/bin/python daemons/btclnd.py > .regtest/daemon.log 2>&1 &
sleep 15
if ! lsof -ti :5012 >/dev/null 2>&1; then
    echo "ERROR: BTCLND daemon failed to start"
    tail -10 .regtest/daemon.log
    exit 1
fi

# 4. Generate seed
echo ">>> Generating wallet seed..."
SEED=$(curl -s -u electrum:electrumz -X POST http://localhost:5012 \
  -H "Content-Type: application/json" \
  -d '{"method":"make_seed","id":1}' | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])")
echo "$SEED" > .regtest/test_seed.txt
export BTCLND_TEST_SEED="$SEED"

# 5. Pre-load wallet and set up channel
echo ">>> Setting up wallet, funding customer, opening channel..."
.venv/bin/python -c "
import asyncio, os, sys, json, hashlib
sys.path.insert(0, 'tests/functional/btclnd')
from utils import LNDTestClient, BitcartDaemonClient, mine_blocks, load_ports, fund_customer_wallet

async def setup():
    ports = load_ports()
    seed = os.environ['BTCLND_TEST_SEED']
    daemon = BitcartDaemonClient()

    customer = LNDTestClient('127.0.0.1', int(ports['CUSTOMER_GRPC']), ports['CUSTOMER_DIR'])
    await customer.connect()
    await customer.wait_for_sync(timeout=30)

    await fund_customer_wallet(customer)
    print(f'Customer funded: {await customer.wallet_balance()} sats')

    for _ in range(60):
        try:
            info = await daemon.call_with_wallet('getinfo', xpub=seed)
            if info.get('block_height', 0) > 0: break
        except: pass
        await asyncio.sleep(1)

    pubkey = info['identity_pubkey']
    wk = hashlib.sha256(seed.strip().encode()).hexdigest()[:16]
    pm = json.load(open(os.path.join(os.getcwd(), '.regtest', 'daemon', 'port_map.json')))
    p2p = pm[wk]['p2p']

    await customer.connect_peer(pubkey, f'127.0.0.1:{p2p}')
    await asyncio.sleep(5)
    await customer.open_channel_sync(pubkey, 500_000)
    mine_blocks(6)
    await asyncio.sleep(5)

    for _ in range(30):
        chs = await customer.list_channels()
        if any(c.active for c in chs):
            print('Channel active!')
            break
        await asyncio.sleep(1)

    await customer.close()

asyncio.run(setup())
"

# 6. Start API
echo ">>> Starting API..."
.venv/bin/uvicorn main:app --port 8000 > .regtest/api.log 2>&1 &
sleep 5
if ! lsof -ti :8000 >/dev/null 2>&1; then
    echo "ERROR: API failed to start"
    tail -10 .regtest/api.log
    exit 1
fi

# 7. Run tests
echo ">>> Running tests..."
.venv/bin/python -m pytest tests/functional/btclnd/test_btclnd_api_flow.py \
  -v -n 0 --no-cov --tb=short \
  --confcutdir=tests/functional/btclnd \
  "$@"
