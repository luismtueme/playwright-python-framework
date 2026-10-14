# Changelog

## 1.0.0

First release of the Python sibling of playwright-typescript-framework.

- Pytest and Playwright, with traces, screenshots, videos, JUnit XML, and a pull-request summary. No Allure and no Behave.
- Page objects, role sessions, an OpenAPI response check, seeded data, quarantine-with-ticket, and a leftover-data check.
- Demo app with the same pages and JSON API as the TypeScript framework.
- UI, API, database, accessibility, performance, property, and visual tests.
- Ruff, mypy, a test-policy linter, a scaffold, and a line-coverage gate on the framework modules.
- Docker Compose with MySQL 8.4, and GitHub Actions for checks, burn-in, shards, quarantine, visuals, and a nightly browser and device matrix.
- Visual baselines for desktop, Pixel 7, and iPhone 15, committed as SHA-256 hashes so CI compares screenshot bytes instead of writing images back.
- Required status checks named Checks, Tests, Visual, and Burn-in, matching the other frameworks.
