all: ci

lint:
	flake8 --select=C --exit-zero
	flake8 --extend-ignore=C901

checkformat:
	black --check .
	isort --check .

format:
	black .
	isort .

test:
	pytest tests/

migrate:
	alembic upgrade head

rollback:
	alembic downgrade -1

migration:
	alembic revision --autogenerate -m "${MESSAGE}"

regtest:
	rm -rf ~/.electrum/regtest
	BTC_DEBUG=true BTC_NETWORK=regtest BTC_SERVER=127.0.0.1:51001:t BTC_LIGHTNING=true python3 daemons/btc.py

testnet:
	BTC_DEBUG=true BTC_NETWORK=testnet BTC_LIGHTNING=true python3 daemons/btc.py

mainnet:
	BTC_DEBUG=true BTC_LIGHTNING=true python3 daemons/btc.py

ci: checkformat lint test