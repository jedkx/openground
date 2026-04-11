.PHONY: verify fmt lint test

verify: lint test
	@echo "OK — verify complete"

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .

test:
	uv run pytest -q
