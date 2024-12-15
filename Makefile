all: ci

lint:
	ruff check

checkformat:
	ruff format --check

format:
	ruff format

test:
	pytest ${TEST_ARGS}

migrate:
	alembic upgrade head

rollback:
	alembic downgrade -1

migration:
	alembic revision --autogenerate -m "${MESSAGE}"

regtest:
	rm -rf ~/.electrum/regtest
	BTC_DEBUG=true BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51002:s BTC_LIGHTNING=true python3 daemons/btc.py

regtestln:
	rm -rf /tmp/bitcartln
	BTC_DEBUG=true BTC_DATA_PATH=/tmp/bitcartln BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51002:s BTC_LIGHTNING=true BTC_LIGHTNING_LISTEN=0.0.0.0:9735 BTC_PORT=5110 python3 daemons/btc.py

testnet:
	BTC_DEBUG=true BTC_NETWORK=testnet BTC_LIGHTNING=true python3 daemons/btc.py

mainnet:
	BTC_DEBUG=true BTC_LIGHTNING=true BTC_NETWORK=mainnet python3 daemons/btc.py

bitcoind:
	tests/functional/bootstrap/start_bitcoind.sh

fulcrum:
	tests/functional/bootstrap/start_fulcrum.sh

functional:
	BTC_LIGHTNING=true FUNCTIONAL_TESTS=true pytest tests/functional/ --cov-append -n 0 ${TEST_ARGS}

ci: checkformat lint test
