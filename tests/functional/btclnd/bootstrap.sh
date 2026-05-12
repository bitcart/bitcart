#!/usr/bin/env bash
# Bootstrap script for BTCLND regtest testing.
# Starts: bitcoind (regtest) + merchant LND + customer LND
# Mines initial blocks and funds the customer wallet.
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Paths
TEST_DIR="$PROJECT_DIR/.regtest"
BITCOIN_DIR="$TEST_DIR/bitcoind"
LND_BIN="${LND_BIN:-$(which lnd || echo "$HOME/.bitcart-btclnd/signet/.lnd-bin/lnd")}"
LNCLI_BIN="${LNCLI_BIN:-$(which lncli || echo "")}"
MERCHANT_DIR="$TEST_DIR/merchant"
CUSTOMER_DIR="$TEST_DIR/customer"

# Ports
BITCOIND_RPC_PORT=18554
MERCHANT_GRPC=11009
MERCHANT_REST=11080
MERCHANT_P2P=19735
CUSTOMER_GRPC=11010
CUSTOMER_REST=11081
CUSTOMER_P2P=19736
RECEIVER_GRPC=11011
RECEIVER_REST=11082
RECEIVER_P2P=19737
RECEIVER_DIR="$TEST_DIR/receiver"

# Clean up from previous runs
cleanup() {
    echo "Cleaning up..."
    screen -S bitcoind-regtest -X quit 2>/dev/null || true
    pkill -f "lnd.*--lnddir=$MERCHANT_DIR" 2>/dev/null || true
    pkill -f "lnd.*--lnddir=$CUSTOMER_DIR" 2>/dev/null || true
    pkill -f "lnd.*--lnddir=$RECEIVER_DIR" 2>/dev/null || true
    sleep 2
}

# Start bitcoind in regtest with compact block filters (needed for LND neutrino)
start_bitcoind() {
    echo "Starting bitcoind (regtest)..."
    mkdir -p "$BITCOIN_DIR"
    screen -S bitcoind-regtest -X quit 2>/dev/null || true
    screen -S bitcoind-regtest -m -d bitcoind \
        -regtest \
        -datadir="$BITCOIN_DIR" \
        -txindex \
        -printtoconsole \
        -rpcuser=doggman \
        -rpcpassword=donkey \
        -rpcallowip=127.0.0.1 \
        -rpcbind=0.0.0.0 \
        -rpcport=$BITCOIND_RPC_PORT \
        -zmqpubrawblock=tcp://127.0.0.1:28332 \
        -zmqpubrawtx=tcp://127.0.0.1:28333 \
        -fallbackfee=0.0002 \
        -blockfilterindex=1 \
        -peerblockfilters=1
    sleep 3
    bcli createwallet test_wallet 2>/dev/null || true
    echo "bitcoind started"
}

# Start an LND node using neutrino mode (connects to bitcoind's p2p port)
start_lnd() {
    local name=$1
    local dir=$2
    local grpc_port=$3
    local rest_port=$4
    local p2p_port=$5

    echo "Starting LND ($name) on gRPC=$grpc_port, P2P=$p2p_port..."
    mkdir -p "$dir"

    "$LND_BIN" \
        --bitcoin.regtest \
        --bitcoin.node=neutrino \
        --neutrino.connect=127.0.0.1:18444 \
        --rpclisten=0.0.0.0:$grpc_port \
        --restlisten=0.0.0.0:$rest_port \
        --listen=0.0.0.0:$p2p_port \
        --lnddir="$dir" \
        --noseedbackup \
        --accept-keysend \
        --debuglevel=info \
        --tlsextradomain=localhost \
        --tlsextraip=0.0.0.0 \
        > "$dir/lnd.log" 2>&1 &

    echo $! > "$dir/lnd.pid"

    # Wait for TLS cert and gRPC port
    for i in $(seq 1 60); do
        if [ -f "$dir/tls.cert" ]; then
            # Check gRPC port
            if nc -z 127.0.0.1 $grpc_port 2>/dev/null; then
                echo "LND ($name) is ready"
                return 0
            fi
        fi
        sleep 0.5
    done
    echo "ERROR: LND ($name) failed to start"
    cat "$dir/lnd.log" | tail -20
    return 1
}

# Initialize an LND wallet (using --noseedbackup, no password needed)
init_lnd_wallet() {
    local name=$1
    local dir=$2
    local grpc_port=$3

    # With --noseedbackup, LND auto-creates a wallet. Wait for it.
    echo "Waiting for LND ($name) wallet..."
    local macaroon="$dir/data/chain/bitcoin/regtest/admin.macaroon"
    for i in $(seq 1 60); do
        if [ -f "$macaroon" ]; then
            echo "LND ($name) wallet ready"
            return 0
        fi
        sleep 0.5
    done
    echo "ERROR: LND ($name) wallet not ready"
    return 1
}

# bitcoin-cli wrapper with wallet and credentials
bcli() {
    bitcoin-cli -datadir="$BITCOIN_DIR" -rpcuser=doggman -rpcpassword=donkey -rpcport=$BITCOIND_RPC_PORT -rpcwallet=test_wallet -regtest "$@"
}

# Mine blocks using bitcoin-cli
mine_blocks() {
    local count=$1
    local addr=${2:-$(bcli getnewaddress)}
    bcli generatetoaddress $count $addr > /dev/null
    echo "Mined $count blocks"
}

# Main
case "${1:-start}" in
    start)
        cleanup
        rm -rf "$TEST_DIR"
        mkdir -p "$TEST_DIR"

        start_bitcoind
        start_lnd "merchant" "$MERCHANT_DIR" $MERCHANT_GRPC $MERCHANT_REST $MERCHANT_P2P
        start_lnd "customer" "$CUSTOMER_DIR" $CUSTOMER_GRPC $CUSTOMER_REST $CUSTOMER_P2P
        start_lnd "receiver" "$RECEIVER_DIR" $RECEIVER_GRPC $RECEIVER_REST $RECEIVER_P2P
        init_lnd_wallet "merchant" "$MERCHANT_DIR" $MERCHANT_GRPC
        init_lnd_wallet "customer" "$CUSTOMER_DIR" $CUSTOMER_GRPC
        init_lnd_wallet "receiver" "$RECEIVER_DIR" $RECEIVER_GRPC

        # Mine initial blocks so coins are spendable
        # First, get the customer's address and mine to it
        sleep 2  # let LND settle
        mine_blocks 105

        echo ""
        echo "=== BTCLND Regtest Environment Ready ==="
        echo "bitcoind RPC:    localhost:$BITCOIND_RPC_PORT (doggman/donkey)"
        echo "Merchant LND:    localhost:$MERCHANT_GRPC (dir: $MERCHANT_DIR)"
        echo "Customer LND:    localhost:$CUSTOMER_GRPC (dir: $CUSTOMER_DIR)"
        echo "Receiver LND:    localhost:$RECEIVER_GRPC (dir: $RECEIVER_DIR)"
        echo ""
        echo "Ports saved to: $TEST_DIR/ports.env"

        # Save port config for tests
        cat > "$TEST_DIR/ports.env" <<EOF
BITCOIND_RPC_PORT=$BITCOIND_RPC_PORT
MERCHANT_GRPC=$MERCHANT_GRPC
MERCHANT_REST=$MERCHANT_REST
MERCHANT_P2P=$MERCHANT_P2P
MERCHANT_DIR=$MERCHANT_DIR
CUSTOMER_GRPC=$CUSTOMER_GRPC
CUSTOMER_REST=$CUSTOMER_REST
CUSTOMER_P2P=$CUSTOMER_P2P
CUSTOMER_DIR=$CUSTOMER_DIR
RECEIVER_GRPC=$RECEIVER_GRPC
RECEIVER_REST=$RECEIVER_REST
RECEIVER_P2P=$RECEIVER_P2P
RECEIVER_DIR=$RECEIVER_DIR
LND_BIN=$LND_BIN
EOF
        ;;
    stop)
        cleanup
        ;;
    mine)
        mine_blocks ${2:-1} ${3:-}
        ;;
    *)
        echo "Usage: $0 {start|stop|mine [count] [address]}"
        exit 1
        ;;
esac
