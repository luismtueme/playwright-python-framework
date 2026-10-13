"""Visual tests render inside the Playwright Docker image so pixels stay stable."""

import os

import pytest


@pytest.fixture(autouse=True)
def _require_docker() -> None:
    if os.environ.get("IN_DOCKER") != "true":
        pytest.fail("Visual tests must run in Docker for stable screenshots: uv run python -m utils.visual")
