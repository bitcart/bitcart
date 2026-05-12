#!/bin/bash
cd /home/user/LND/bitcart-admin
export BITCART_ADMIN_API_URL=http://127.0.0.1:8000
exec yarn start
