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
	alembic revision --autogenerate -m ${MESSAGE}

ci: checkformat lint test