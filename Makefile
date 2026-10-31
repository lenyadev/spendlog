.PHONY: check fix test

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

fix:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest -v