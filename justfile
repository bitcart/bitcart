set no-exit-message := true

test-args := env("TEST_ARGS", "")

[private]
default:
    @just --list --unsorted --justfile {{ justfile() }}

# python-level tasks

# run api service
[group("Services")]
dev-api:
    uvicorn main:app --ws websockets-sansio --timeout-graceful-shutdown 1 --reload

# run worker service
[group("Services")]
worker:
    python3 worker.py

# run api service in production
[group("Services")]
prod-api:
    gunicorn -c gunicorn.conf.py main:app

# run migrations and start api service in production
[group("Services")]
prod-api-up: db-migrate prod-api

# run coin daemons
[group("Services")]
daemon coin:
    python3 daemons/{{ coin }}.py

# run linters with autofix
[group("Linting")]
lint:
    ruff format . && ruff check --fix .

# run linters (check only)
[group("Linting")]
lint-check:
    ruff format --check . && ruff check .

# run type checking
[group("Linting")]
lint-types:
    mypy api tests main.py worker.py

# run tests
[group("Testing")]
test *args:
    pytest {{ trim(test-args + " " + args) }}

# run functional tests
[group("Testing")]
functional *args:
    BTC_LIGHTNING=true pytest tests/functional/ --cov-append -n 0 {{ trim(test-args + " " + args) }}

# create new migration
[group("Database")]
db-migration MESSAGE:
    alembic revision --autogenerate -m "{{ MESSAGE }}"

# run alembic upgrade
[group("Database")]
db-migrate:
    alembic upgrade head

# run alembic downgrade
[group("Database")]
db-rollback:
    alembic downgrade -1

# run ci checks (without tests)
[group("CI")]
ci-lint: lint-check lint-types

# run ci checks
[group("CI")]
ci *args: ci-lint (test args)

# btc-setup tasks

# start electrum regtest daemon
[group("BTC setup")]
regtest:
    rm -rf ~/.electrum/regtest
    BTC_DEBUG=true BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51002:s BTC_LIGHTNING=true BTC_LIGHTNING_GOSSIP=true just daemon btc

# start electrum regtest daemon (lightning node)
[group("BTC setup")]
regtestln:
    rm -rf /tmp/bitcartln
    BTC_DEBUG=true BTC_DATA_PATH=/tmp/bitcartln BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51002:s BTC_LIGHTNING=true BTC_LIGHTNING_GOSSIP=true BTC_LIGHTNING_LISTEN=0.0.0.0:9735 BTC_PORT=5110 just daemon btc

# start electrum testnet daemon
[group("BTC setup")]
testnet:
    BTC_DEBUG=true BTC_NETWORK=testnet BTC_LIGHTNING=true just daemon btc

# start electrum mainnet daemon
[group("BTC setup")]
mainnet:
    BTC_DEBUG=true BTC_LIGHTNING=true BTC_NETWORK=mainnet just daemon btc

# start bitcoind
[group("BTC setup")]
bitcoind:
    tests/functional/bootstrap/start_bitcoind.sh

# start fulcrum
[group("BTC setup")]
fulcrum:
    tests/functional/bootstrap/start_fulcrum.sh
