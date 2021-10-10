#!/usr/bin/env bash
if ! [[ -x "$(command -v Fulcrum)" ]]; then
    echo "Please get Fulcrum from https://github.com/cculianu/Fulcrum/releases"
    exit 1
fi
set -eux pipefail
export HOME=~
export SSL_KEYFILE=$HOME/.fulcrum/key.pem
export SSL_CERTFILE=$HOME/.fulcrum/cert.pem
cd
rm -rf ~/.fulcrum
mkdir -p ~/.fulcrum
cat >~/.fulcrum/fulcrum.conf <<EOF
datadir=$HOME/.fulcrum/db
bitcoind = 127.0.0.1:18554
rpcuser = doggman
rpcpassword = donkey
ssl = 0.0.0.0:51002
key = $SSL_KEYFILE
cert = $SSL_CERTFILE
peering = false
debug = true
EOF
openssl req -newkey rsa:2048 -sha256 -nodes -x509 -days 365 -subj "/O=Fulcrum" -keyout "${SSL_KEYFILE}" -out "${SSL_CERTFILE}"
Fulcrum $HOME/.fulcrum/fulcrum.conf
