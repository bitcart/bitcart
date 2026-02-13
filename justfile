[private]
default:
    @just --list --unsorted --justfile {{ justfile() }}

# python-level tasks

# run api service
dev-api:
    uvicorn main:app --ws websockets-sansio --timeout-graceful-shutdown 1 --reload

# run worker service
worker:
    python3 worker.py

# run api service in production
prod-api:
    gunicorn -c gunicorn.conf.py main:app

# run migrations and start api service in production
prod-up: db_migrate prod-api

# run linters with autofix
lint:
    ruff format . && ruff check --fix .

# run linters (check only)
lint_check:
    ruff format --check . && ruff check .

# run type checking
lint_types:
    mypy api tests main.py worker.py

# run tests
test *TEST_ARGS:
    pytest {{ TEST_ARGS }}

# run functional tests
functional *TEST_ARGS:
    BTC_LIGHTNING=true pytest tests/functional/ --cov-append -n 0 {{ TEST_ARGS }}

# create new migration
db_migration MESSAGE:
    alembic revision --autogenerate -m "{{ MESSAGE }}"

# run alembic upgrade
db_migrate:
    alembic upgrade head

# run alembic downgrade
db_rollback:
    alembic downgrade -1

# run ci checks
ci: lint_check lint_types test

# btc-setup tasks

# start electrum regtest daemon
[group("BTC setup")]
regtest:
    rm -rf ~/.electrum/regtest
    BTC_DEBUG=true BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51002:s BTC_LIGHTNING=true BTC_LIGHTNING_GOSSIP=true python3 daemons/btc.py

# start electrum regtest daemon (lightning node)
[group("BTC setup")]
regtestln:
    rm -rf /tmp/bitcartln
    BTC_DEBUG=true BTC_DATA_PATH=/tmp/bitcartln BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51002:s BTC_LIGHTNING=true BTC_LIGHTNING_GOSSIP=true BTC_LIGHTNING_LISTEN=0.0.0.0:9735 BTC_PORT=5110 python3 daemons/btc.py

# start electrum testnet daemon
[group("BTC setup")]
testnet:
    BTC_DEBUG=true BTC_NETWORK=testnet BTC_LIGHTNING=true python3 daemons/btc.py

# start electrum mainnet daemon
[group("BTC setup")]
mainnet:
    BTC_DEBUG=true BTC_LIGHTNING=true BTC_NETWORK=mainnet python3 daemons/btc.py

# start bitcoind
[group("BTC setup")]
bitcoind:
    tests/functional/bootstrap/start_bitcoind.sh

# start fulcrum
[group("BTC setup")]
fulcrum:
    tests/functional/bootstrap/start_fulcrum.sh
