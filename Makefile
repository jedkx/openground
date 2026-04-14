.PHONY: verify fmt lint test test-cov

verify: lint test
	@echo "OK — verify complete"

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .

test:
	uv run pytest -q

test-cov:
	uv run pytest -q --cov=openground --cov-report=xml --cov-report=term-missing
