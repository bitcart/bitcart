# BTCLND Functional Tests

End-to-end payment tests for the BTCLND daemon using Bitcoin regtest.

## Prerequisites

- `bitcoind` installed and on PATH
- `lnd` binary available (auto-detected from the BTCLND daemon's download location)
- `screen` installed (for running bitcoind in background)
- `nc` (netcat) installed

## Quick Start

```bash
# Terminal 1: Start the regtest environment (bitcoind + 2 LND nodes)
just btclnd-regtest-env

# Terminal 2: Start the BTCLND daemon in regtest mode
just btclnd-regtest-daemon

# Terminal 3: Run the tests
# First, set the merchant wallet seed (generate via the daemon)
export BTCLND_TEST_SEED="your 24 word seed here"
just btclnd-functional
```

## Test Scenarios

1. **Lightning Payment** - Create invoice → pay via lightning → verify payment detected
2. **On-chain Payment** - Create invoice → send on-chain → mine block → verify
3. **Partial On-chain Payments** - Create invoice → send two partial payments → mine → verify total
4. **Balance Checks** - Verify on-chain and lightning balances are reported correctly
5. **Node Info** - Verify getinfo, nodeid, channel list

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│   Customer LND  │────│  Merchant LND     │
│   (payer)       │     │  (via BTCLND      │
│   port 11010    │     │   daemon)         │
└────────┬────────┘     │  port 11009       │
         │              └────────┬──────────┘
         │                       │
    ┌────┴───────────────────────┴────┐
    │         bitcoind (regtest)       │
    │         port 18554 (RPC)         │
    │         port 18444 (P2P)         │
    └──────────────────────────────────┘
```

## Manual Block Mining

```bash
# Mine blocks during tests
tests/functional/btclnd/bootstrap.sh mine 6
```

## Cleanup

```bash
just btclnd-regtest-env-stop
```
