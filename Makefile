all: ci

lint:
	flake8

checkformat:
	black --check .
	isort --check .

format:
	black .
	isort .

test:
	pytest tests/ ${TEST_ARGS}

migrate:
	alembic upgrade head

rollback:
	alembic downgrade -1

migration:
	alembic revision --autogenerate -m "${MESSAGE}"

regtest:
	rm -rf ~/.electrum/regtest
	BTC_DEBUG=true BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51001:t BTC_LIGHTNING=true python3 daemons/btc.py

regtestln:
	rm -rf /tmp/bitcartln
	BTC_DEBUG=true BTC_DATA_PATH=/tmp/bitcartln BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51001:t BTC_LIGHTNING=true BTC_LIGHTNING_LISTEN=0.0.0.0:9735 BTC_PORT=5110 python3 daemons/btc.py

testnet:
	BTC_DEBUG=true BTC_NETWORK=testnet BTC_LIGHTNING=true python3 daemons/btc.py

mainnet:
	BTC_DEBUG=true BTC_LIGHTNING=true BTC_LIGHTNING_GOSSIP=true BTC_NETWORK=mainnet python3 daemons/btc.py

bitcoind:
	tests/functional/bootstrap/start_bitcoind.sh

electrumx:
	tests/functional/bootstrap/start_electrumx.sh

functional:
	pytest tests/functional/ --cov-append ${TEST_ARGS}

ci: checkformat lint test