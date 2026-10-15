# GitHub Actions

Two workflows. Neither publishes an Allure report.

## Playwright (`.github/workflows/playwright.yml`)

Runs on pull requests, on pushes to `main`, and on demand from the Actions tab.

| Job | What it does |
| --- | --- |
| `Checks` | Ruff, mypy, test-policy lint, generated types, unit tests at 90% coverage, `pip-audit` |
| `Burn-in` | On pull requests, repeats changed test files 10 times with retries off. Shared framework edits (`pages/`, `utils/`, `config/`, `demo_app/`, `contracts/`, `tests/conftest.py`) skip the burn-in, because the shard jobs already run the suite. Needs full git history (`fetch-depth: 0`) |
| `Tests (shard N/4)` | The suite split across four machines, each with MySQL 8.4. Shard 1 also runs quarantined tests (non-blocking). Every shard checks for leftover rows. JUnit and `report.json` are uploaded |
| `Tests` | Requires all four shard reports and fails if any shard failed |
| `Visual` | Screenshot comparison inside the Playwright Docker image against the committed `*.png.sha256` baselines. Uploads `*-actual.png` on failure |
| `Summary` | Posts or updates the pull-request comment that starts with `<!-- playwright-summary -->` |

`Checks`, `Burn-in`, `Tests`, and `Visual` are the required status checks for merging into `main`, the same set as [playwright-typescript-framework](https://github.com/luismtueme/playwright-typescript-framework). `Burn-in` is skipped on pushes to `main`, which GitHub counts as passing. The ruleset also blocks force-pushes and branch deletion, requires a linear history, and allows only squash merges. Pull requests must resolve review threads. No approving review is required.

Nightly is not a required check.

## Nightly (`.github/workflows/nightly.yml`)

06:00 UTC, and `workflow_dispatch`.

- Chromium, Firefox, and WebKit on the desktop viewport.
- Pixel 7 and iPhone 15 on Chromium, and iPhone 15 on WebKit. Firefox has no mobile emulation, so it is not in the device matrix.
- Each browser job runs `pytest tests` with `--browser` (and `--device` for the phones) and MySQL 8.4, same database settings as the pull-request shards. Unit tests stay on Checks.
- The same visual comparison as the pull-request workflow.

## Local Docker

```bash
docker compose run --build --rm tests
```

Compose sets `DB_HOST=mysql`, so the database tests run. The visual runner is separate: `uv run python -m utils.visual`.
