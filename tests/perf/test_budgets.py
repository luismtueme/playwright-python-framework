"""Performance budgets. The measured values are written next to the test output."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

from config import ROOT
from utils.performance import measure_page, over_budget

_BUDGETS = json.loads((ROOT / "config" / "performance_budgets.json").read_text(encoding="utf-8"))
_PAGES = ("/", "/login", "/items")
pytestmark = pytest.mark.perf


def _budget_for(path: str) -> dict[str, float]:
    pages = _BUDGETS.get("pages") or {}
    return {**_BUDGETS["default"], **pages.get(path, {})}


@pytest.mark.parametrize("path", _PAGES)
def test_page_loads_within_budget(page: Page, browser_name: str, path: str, output_path: str) -> None:
    if browser_name != "chromium":
        pytest.skip("LCP and CLS are only measured in Chromium")
    page.goto(path)
    metrics = measure_page(page)
    budget = _budget_for(path)
    destination = Path(output_path) / "performance.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({"path": path, "metrics": metrics, "budget": budget}, indent=2), encoding="utf-8")
    assert over_budget(metrics, budget) == [], f"metrics: {metrics}"
