# Contributing

The rules below are the same ones the TypeScript framework uses, mapped onto pytest. Read [AGENTS.md](AGENTS.md) before adding a test.

## Setup

```bash
uv sync
uv run playwright install chromium
cp .env.example .env
```

Run `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest unit`, and `uv run python -m utils.lint_tests` before you push. `make lint typecheck unit` is the same list.

## Tests

- Import fixtures from `tests/conftest.py`. A test does not launch its own browser, build its own API client, or log in through the UI, except the login tests.
- Put the test in `tests/ui`, `tests/api`, `tests/db`, `tests/perf`, or `tests/visual`.
- Markers (`smoke`, `api`, `db`, `a11y`, `visual`, `perf`, `quarantine`) describe the test. They do not go in the function name or the docstring.
- New markers are added to `utils/lint_tests.py` and to `pyproject.toml`. The linter rejects anything else.
- The default role is admin. `@pytest.mark.role("viewer")` and `@pytest.mark.role("anonymous")` are the other two. Sessions are created once per role and reused.
- Quarantine a flaky test with `@pytest.mark.quarantine` and `@pytest.mark.issue("QA-123")`. Quarantine still runs. It does not fail the main job. Do not use a bare `pytest.skip` or `@pytest.mark.skip`.
- Data a test creates is deleted by `track_item` or `create_item`. `uv run python -m utils.check_leftover_data` fails CI when rows remain.
- No `page.wait_for_timeout()`. No `networkidle`. Assert on a locator, or use `expect_poll` for a value that is not on the page.
- API responses, including ones the page fires, are checked against `contracts/openapi.yaml`. Opt out with `@pytest.mark.contract(False)` only when the test stubs the network.
- Page objects expose locators and actions. Assertions stay in the test. Prefer `get_by_role` and `get_by_label`.
- `TEST_SEED` feeds `create_item()` and Hypothesis. Do not call `random.random()` for data the test needs to reproduce.

## A change to the contract

Edit `contracts/openapi.yaml`, then:

```bash
uv run python -m utils.generate_api_types
uv run python -m utils.generate_api_types --check
```

Commit `contracts/models.py` with the spec.

## A new page

```bash
uv run python -m utils.scaffold page Settings --path /settings
```

That writes the page object, a smoke test, the fixture, and an accessibility check. Fill in the locators. Do not hand-roll the registration and forget the anchors in `tests/conftest.py`.

## Visual baselines

Update them inside Docker and commit the PNGs:

```bash
uv run python -m utils.visual --update
```

Do not commit screenshots taken on a laptop. The visual job compares against the Playwright image.

## Secrets

Credentials and database passwords come from the environment or `.env`. `.env` is git-ignored. Do not put a secret in `config/test_config.json`.
