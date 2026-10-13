.PHONY: install lint format typecheck unit test lint-tests types visual docker

install:
	uv sync
	uv run playwright install chromium

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run python -m utils.lint_tests
	uv run python -m utils.generate_api_types --check

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy

unit:
	uv run pytest unit --cov=config --cov=demo_app --cov=utils --cov=contracts --cov-fail-under=90

lint-tests:
	uv run python -m utils.lint_tests

types:
	uv run python -m utils.generate_api_types --check

test:
	HEADLESS=$${HEADLESS:-true} uv run pytest -m "not visual"

visual:
	uv run python -m utils.visual

docker:
	docker compose run --build --rm tests
