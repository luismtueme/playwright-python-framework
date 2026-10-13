# GitHub Actions

Two workflows. Neither publishes an Allure report.

## Playwright (`.github/workflows/playwright.yml`)

Runs on pull requests and on pushes to `main`.

| Job | What it does |
| --- | --- |
| `checks` | Ruff, mypy, test-policy lint, generated types, unit tests at 90% coverage, `pip-audit` |
| `burn-in` | On pull requests, repeats changed test files 10 times with retries off. Shared framework edits (`pages/`, `utils/`, `config/`, `demo_app/`, `contracts/`, `tests/conftest.py`) skip the burn-in, because the shard job already runs the suite |
| `tests` | Four pytest-split shards on Chromium, with MySQL 8.4. After each shard, leftover rows fail the job. JUnit and `report.json` are uploaded |
| `quarantine` | `PW_SUITE=quarantine`. `continue-on-error` so a known flake does not fail the check |
| `visual` | Official Playwright Python image. Desktop, Pixel 7, and iPhone 15. Needs committed baselines from `uv run python -m utils.visual --update` |
| `summary` | Posts or updates the pull-request comment that starts with `<!-- playwright-summary -->` |

The Playwright image tag in the Dockerfile and in the visual job is `v1.63.0-noble`, matching the locked `playwright` package. Bump both together when Playwright is upgraded.

## Nightly (`.github/workflows/nightly.yml`)

06:00 UTC, and `workflow_dispatch`.

- Chromium, Firefox, and WebKit on the desktop viewport.
- Pixel 7 and iPhone 15 on Chromium, and iPhone 15 on WebKit. Firefox has no mobile emulation, so it is not in the device matrix.
- The same visual job as the pull-request workflow.

## Local Docker

```bash
docker compose run --build --rm tests
```

Compose sets `DB_HOST=mysql`, so the database tests run. The visual runner is separate: `uv run python -m utils.visual`.
