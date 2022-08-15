#!/usr/bin/env bash
set -eu

bitcoin_cli="/opt/bitcoin-cash-node/bin/bitcoin-cli -rpcwallet=test_wallet -rpcuser=doggman -rpcpassword=donkey -rpcport=18554 -regtest"

function new_blocks()
{
    $bitcoin_cli generatetoaddress $1 $($bitcoin_cli getnewaddress)
}

function pay_to()
{
    $bitcoin_cli generatetoaddress $1 $2
}

function send_to()
{
    $bitcoin_cli sendtoaddress $1 $2
}

if [[ $# -eq 0 ]]; then
    echo "syntax: startup|sendtoaddress|newblock|newblocks|generate|newaddress|newtx"
    exit 1
fi

if [[ $1 == "startup" ]]; then
    pay_to $2 $3
    new_blocks 151
fi

if [[ $1 == "sendtoaddress" ]]; then
    send_to $2 $3
fi

if [[ $1 == "newblock" ]]; then
    new_blocks 1
fi

if [[ $1 == "newblocks" ]]; then
    new_blocks $2
fi

if [[ $1 == "generate" ]]; then
    pay_to $2 $3
fi

if [[ $1 == "newaddress" ]]; then
    $bitcoin_cli getnewaddress
fi

if [[ $1 == "newtx" ]]; then
    block=$($bitcoin_cli generatetoaddress 1 $2 | jq -r '.[0]')
    tx=$($bitcoin_cli getblock $block | jq -r '.tx | .[0]')
    echo $tx
fi
