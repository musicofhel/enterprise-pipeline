.PHONY: dev test test-integration test-eval lint typecheck format infra infra-down install

install:
	pip install -e ".[dev,eval]"
	python -m spacy download en_core_web_sm

dev:
	uvicorn src.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/unit -v --tb=short

test-integration:
	pytest tests/integration -v --tb=short -m integration

test-eval:
	pytest tests/eval -v --tb=short -m eval

lint:
	ruff check src tests

typecheck:
	mypy src

format:
	ruff format src tests
	ruff check --fix src tests

infra:
	docker compose up -d qdrant langfuse-db langfuse redis

infra-down:
	docker compose down

all-tests: lint typecheck test
