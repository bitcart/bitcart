#!/bin/bash
cd /home/user/LND/bitcart-store
export NUXT_PORT=4001
export BITCART_STORE_API_URL=http://127.0.0.1:8000
exec yarn start
