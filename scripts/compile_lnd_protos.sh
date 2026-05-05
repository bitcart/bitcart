#!/bin/bash
# Download and compile LND proto files for Python gRPC
# Usage: ./scripts/compile_lnd_protos.sh [LND_VERSION]
#
# Compiles LND proto files into a flat package structure under daemons/lnd_proto/
# All generated files live directly in daemons/lnd_proto/ (no sub-packages)
# to avoid protobuf descriptor pool path issues.

set -e

LND_VERSION="${1:-v0.20.1-beta}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROTO_OUT_DIR="$PROJECT_DIR/daemons/lnd_proto"
TEMP_DIR=$(mktemp -d)

echo "Compiling LND proto files for version $LND_VERSION"
echo "Output directory: $PROTO_OUT_DIR"

# Clean output directory (preserve __init__.py)
find "$PROTO_OUT_DIR" -name '*_pb2*.py' -delete 2>/dev/null || true

# Download LND proto files - flatten into one directory
echo "Downloading LND proto files..."
LND_PROTO_BASE="https://raw.githubusercontent.com/lightningnetwork/lnd/${LND_VERSION}/lnrpc"

mkdir -p "$TEMP_DIR/protos"
curl -sL "$LND_PROTO_BASE/lightning.proto" -o "$TEMP_DIR/protos/lightning.proto"
curl -sL "$LND_PROTO_BASE/walletunlocker.proto" -o "$TEMP_DIR/protos/walletunlocker.proto"
curl -sL "$LND_PROTO_BASE/stateservice.proto" -o "$TEMP_DIR/protos/stateservice.proto"
curl -sL "$LND_PROTO_BASE/invoicesrpc/invoices.proto" -o "$TEMP_DIR/protos/invoices.proto"
curl -sL "$LND_PROTO_BASE/routerrpc/router.proto" -o "$TEMP_DIR/protos/router.proto"
curl -sL "$LND_PROTO_BASE/walletrpc/walletkit.proto" -o "$TEMP_DIR/protos/walletkit.proto"
curl -sL "$LND_PROTO_BASE/chainrpc/chainnotifier.proto" -o "$TEMP_DIR/protos/chainnotifier.proto"
curl -sL "$LND_PROTO_BASE/signrpc/signer.proto" -o "$TEMP_DIR/protos/signer.proto"

# Download Google API proto dependencies
echo "Downloading Google API proto dependencies..."
mkdir -p "$TEMP_DIR/protos/google/api"
GOOGLE_API_BASE="https://raw.githubusercontent.com/googleapis/googleapis/master/google/api"
curl -sL "$GOOGLE_API_BASE/annotations.proto" -o "$TEMP_DIR/protos/google/api/annotations.proto"
curl -sL "$GOOGLE_API_BASE/http.proto" -o "$TEMP_DIR/protos/google/api/http.proto"

# Fix imports in proto files that reference sub-directories
# e.g., invoices.proto has: import "lightning.proto" - this is already flat
# But some may have: import "lnrpc/lightning.proto" - need to fix
echo "Patching proto file imports..."
for f in "$TEMP_DIR/protos/"*.proto; do
    # Remove sub-directory prefixes from imports (e.g., "lnrpc/" or "routerrpc/")
    sed -i 's|import "lnrpc/|import "|g' "$f"
    sed -i 's|import "invoicesrpc/|import "|g' "$f"
    sed -i 's|import "routerrpc/|import "|g' "$f"
    sed -i 's|import "walletrpc/|import "|g' "$f"
    sed -i 's|import "chainrpc/|import "|g' "$f"
    sed -i 's|import "signrpc/|import "|g' "$f"
done

# Verify downloaded files
for f in "$TEMP_DIR/protos/lightning.proto" "$TEMP_DIR/protos/walletunlocker.proto" \
         "$TEMP_DIR/protos/google/api/annotations.proto"; do
    if [ ! -s "$f" ]; then
        echo "ERROR: Failed to download $f"
        exit 1
    fi
done

echo "Compiling proto files..."
PROTO_FILES=(
    lightning.proto
    walletunlocker.proto
    stateservice.proto
    invoices.proto
    router.proto
    walletkit.proto
    chainnotifier.proto
    signer.proto
)

for proto in "${PROTO_FILES[@]}"; do
    echo "  Compiling $proto..."
    python -m grpc_tools.protoc \
        --proto_path="$TEMP_DIR/protos" \
        --python_out="$PROTO_OUT_DIR" \
        --grpc_python_out="$PROTO_OUT_DIR" \
        "$TEMP_DIR/protos/$proto"
done

# Fix imports: grpc_tools generates bare "import X_pb2" but we need "from lnd_proto import X_pb2"
echo "Fixing imports in generated files..."
PB2_MODULES=(lightning walletunlocker stateservice invoices router walletkit chainnotifier signer)
for f in "$PROTO_OUT_DIR"/*_pb2*.py; do
    for mod in "${PB2_MODULES[@]}"; do
        sed -i "s/^import ${mod}_pb2/from lnd_proto import ${mod}_pb2/" "$f"
    done
done

# Create __init__.py
touch "$PROTO_OUT_DIR/__init__.py"

# Cleanup
rm -rf "$TEMP_DIR"

echo "Done! Proto stubs generated in $PROTO_OUT_DIR"
echo "Generated files:"
find "$PROTO_OUT_DIR" -name '*.py' | sort
