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

ci: checkformat lint test