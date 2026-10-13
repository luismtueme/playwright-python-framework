# Agent notes

This is a pytest port of playwright-typescript-framework. Allure, Behave, and the Node Playwright planner, generator, and healer agents are out of scope. Do not add them.

## How a test is put together

```text
pytest -> tests/conftest.py -> pages/ and utils/api_client.py -> demo app or BASE_URL
                            -> contracts/openapi.yaml
                            -> test-results/ (trace, screenshot, video, junit, report.json)
```

- Fixtures live in `tests/conftest.py`. Tests ask for `page`, `items_page`, `api`, `create_item`, and so on.
- `pages/` has locators and actions only. `expect(...)` belongs in the test.
- Roles: admin (default), `role("viewer")`, `role("anonymous")`. Storage state is saved per role after one API login.
- Markers are the allowlist in `utils/lint_tests.py`. Unknown markers fail `python -m utils.lint_tests`.
- Quarantine requires `issue("QA-123")`. Bare `skip` fails the linter. `pytest.skip` nested under an `if` is the runtime escape hatch (for example, a browser that cannot emulate a phone).
- `create_item` / `track_item` delete rows in fixture teardown. Leftover rows fail `utils/check_leftover_data.py`.
- Contract checks run on the API client and on responses the page receives. `contract(False)` opts out.
- `wait_for_timeout` and `networkidle` fail the linter. Use locator assertions or `tests/support.py` `expect_poll`.
- `TEST_SEED` is printed on the test via `user_properties`. Hypothesis examples use that seed.

## Demo app

`demo_app/` is a stdlib HTTP server: `/`, `/login`, `/items`, and `/api/login`, `/api/me`, `/api/items`. Memory store, or MySQL `items` when `DB_HOST` is set. Pytest starts it unless `BASE_URL` is set. Demo passwords only work when `BASE_URL` is empty. A real app must set `APP_USERNAME` and `APP_PASSWORD`.

## Commands that must pass

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest unit
uv run python -m utils.lint_tests
uv run python -m utils.generate_api_types --check
HEADLESS=true uv run pytest -m "not visual"
```

Visual tests need Docker: `uv run python -m utils.visual`.

## Generated files

`contracts/models.py` is generated. Change the OpenAPI document and regenerate. `utils/vendor/axe.min.js` is vendored axe-core (MPL-2.0); do not reformat it.

## What not to edit

Do not change the TypeScript, Java, or JavaScript sibling repositories from this repo. Do not add a GitHub Pages Allure deploy.
