# Changelog

## 1.0.0

First release of the Python sibling of playwright-typescript-framework.

- Pytest and Playwright, with traces, screenshots, videos, JUnit XML, and a pull-request summary. No Allure and no Behave.
- Page objects, role sessions, an OpenAPI response check, seeded data, quarantine-with-ticket, and a leftover-data check.
- Demo app with the same pages and JSON API as the TypeScript framework.
- UI, API, database, accessibility, performance, property, and visual tests.
- Ruff, mypy, a test-policy linter, a scaffold, and a line-coverage gate on the framework modules.
- Docker Compose with MySQL 8.4, and GitHub Actions for checks, burn-in, shards, quarantine, visuals, and a nightly browser and device matrix.

Visual baselines are produced by `uv run python -m utils.visual --update` inside the Playwright image. They are committed after that command has been run.
