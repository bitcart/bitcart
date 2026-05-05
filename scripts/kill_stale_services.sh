#!/bin/bash
# Kill any stale Bitcart services from previous runs.
# Used as a PyCharm "Before Launch" external tool.

# Kill ALL uvicorn and worker processes (catches --reload parents, children, and plain instances)
pids=$(pgrep -f "uvicorn main:app" 2>/dev/null)
if [ -n "$pids" ]; then
    echo "Killing uvicorn processes: $pids"
    echo "$pids" | xargs kill -9 2>/dev/null
fi
pids=$(pgrep -f "python.*worker.py" 2>/dev/null)
if [ -n "$pids" ]; then
    echo "Killing worker processes: $pids"
    echo "$pids" | xargs kill -9 2>/dev/null
fi

# Kill Bitcart services by port (force kill to ensure socket release)
for port in 5000 5012 8000 3000 4001; do
    pids=$(lsof -ti :"$port" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "Killing stale process on port $port (pid=$pids)"
        echo "$pids" | xargs kill -9 2>/dev/null
    fi
done

# Wait for sockets to fully release
sleep 1

# Verify all ports are free
for port in 5000 5012 8000 3000 4001; do
    if lsof -ti :"$port" >/dev/null 2>&1; then
        echo "WARNING: Port $port still in use, force killing"
        lsof -ti :"$port" | xargs kill -9 2>/dev/null
        sleep 0.5
    fi
done

# Kill any orphaned LND processes from previous daemon runs
pids=$(pgrep -f "lnd.*--bitcoin.active.*--lnddir=.*bitcart-btclnd" 2>/dev/null)
if [ -n "$pids" ]; then
    echo "Killing orphaned LND processes: $pids"
    echo "$pids" | xargs kill 2>/dev/null
    sleep 1
    echo "$pids" | xargs kill -9 2>/dev/null
fi

# Kill any orphaned per-wallet Tor processes from previous daemon runs
pids=$(pgrep -f "tor.*-f.*bitcart-btclnd.*torrc" 2>/dev/null)
if [ -n "$pids" ]; then
    echo "Killing orphaned Tor processes: $pids"
    echo "$pids" | xargs kill 2>/dev/null
    sleep 1
    echo "$pids" | xargs kill -9 2>/dev/null
fi

echo "Ports cleared"
