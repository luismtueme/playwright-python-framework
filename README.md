# Playwright Python Framework

Pytest and Playwright for UI, API, database, accessibility, and visual checks. This is the Python sibling of [playwright-typescript-framework](https://github.com/luismtueme/playwright-typescript-framework). The same ideas show up in [playwright-cucumber-typescript](https://github.com/luismtueme/playwright-cucumber-typescript), [playwright-cucumber-automation](https://github.com/luismtueme/playwright-cucumber-automation), [selenium-java-cucumber](https://github.com/luismtueme/selenium-java-cucumber), and [appium-java-cucumber](https://github.com/luismtueme/appium-java-cucumber).

There is no Allure and no Behave. Failures are the pytest output, a JUnit XML file, and Playwright traces, screenshots, and videos. Open a failed test with `uv run playwright show-trace test-results/<test>/trace.zip`.

The suite runs against a small demo app (login, a form, and an items API) so the examples pass on a fresh clone. Point `BASE_URL` at your application when you adopt the framework.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker, only for visual tests and the compose database run

## Setup

```bash
uv sync
uv run playwright install chromium
cp .env.example .env
```

Leave `BASE_URL` empty. Pytest starts the demo app. Run it yourself with `uv run python -m demo_app` (http://127.0.0.1:4173). Admin is `demo` / `demo-password`. Viewer is `viewer` / `viewer-password`.

## Run

```bash
uv run pytest                  # unit tests and the suite, visual and quarantine excluded
uv run pytest -m smoke         # critical path
uv run pytest -m "not visual"  # everything except screenshots
uv run pytest unit             # framework unit tests
make test
```

`HEADLESS` defaults to the value in `config/test_config.json` locally (`false`) and to `true` when `CI` is set. Set `HEADLESS=true` on a machine without a display.

Database tests run only when `DB_HOST` is set:

```bash
docker compose run --build --rm tests
```

That starts MySQL 8.4 and runs the suite, including the `db` tests.

## Reports

Pytest writes `test-results/`. A failure keeps a trace, a screenshot, and a video. `test-results/report.json` is a short machine-readable summary, and `utils/pr_summary.py` turns it into the pull-request comment.

## Project map

| Path | What it is |
| --- | --- |
| `tests/conftest.py` | Browser, role sessions, API client, contract checks, cleanup |
| `pages/` | Locators and actions. Assertions stay in tests |
| `demo_app/` | The app the examples hit |
| `contracts/openapi.yaml` | Response contract. Regenerate `contracts/models.py` when it changes |
| `utils/` | API and database clients, lint, scaffold, visual runner |
| `unit/` | Tests for the framework itself |
| `config/` | Env, `.env`, then `config/test_config.json` |

## Conventions

Markers replace tags in the test name: `smoke`, `api`, `db`, `a11y`, `visual`, `perf`, `quarantine`. The default role is admin. Use `@pytest.mark.role("viewer")` or `"anonymous"`. Login happens once per role through the API. UI login is only for the login tests.

`create_item()` deletes the row after the test. CI fails if rows remain (`uv run python -m utils.check_leftover_data`).

Quarantine still runs and does not fail the main job. It needs `@pytest.mark.issue("QA-123")`. A bare `pytest.skip` or `@pytest.mark.skip` is rejected. A `pytest.skip` inside a condition is allowed when the condition is only known at runtime (browser name).

Do not call `page.wait_for_timeout()` or wait for `networkidle`. Use a locator assertion, or `expect_poll` from `tests/support.py` for a value that is not on the page.

Every API response is checked against `contracts/openapi.yaml`, including calls the page makes. Tests that fake responses with `page.route` opt out with `@pytest.mark.contract(False)`.

`TEST_SEED` drives `create_item()` and Hypothesis. The seed is recorded on the test.

## Scaffold

```bash
uv run python -m utils.scaffold page Settings --path /settings
uv run python -m utils.scaffold spec checkout --page items
uv run python -m utils.codegen /items
```

## Visual tests

Screenshots are compared with Pillow (a few pixels of slack for anti-aliasing). They only run inside the Playwright Docker image, so a laptop and CI render the same pixels.

```bash
uv run python -m utils.visual --update   # write baselines, then commit tests/visual/__screenshots__/
uv run python -m utils.visual            # compare
```

Baselines are not in the repo until that Docker command has been run once. Until then the visual job fails with "Missing baseline".

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest unit --cov=config --cov=demo_app --cov=utils --cov=contracts --cov-fail-under=90
uv run python -m utils.lint_tests
uv run python -m utils.generate_api_types --check
```

GitHub Actions runs those checks, a 10-times burn-in of changed tests, a four-way shard of the suite, a non-blocking quarantine job, a leftover-data check, and the visual job. Nightly runs Chromium, Firefox, and WebKit, plus Pixel 7 and iPhone 15. See [GITHUB_ACTIONS_GUIDE.md](GITHUB_ACTIONS_GUIDE.md).

## License

MIT. Copyright 2026 Luis Alberto Morales Tueme.
