"""Base class for page objects.

Page objects expose Playwright locators and user-level actions. Keep assertions
in the tests, and rely on Playwright's auto-waiting rather than explicit waits.
"""

from __future__ import annotations

from playwright.sync_api import Page


class BasePage:
    """Path relative to the base URL, overridden by each page."""

    path = "/"

    def __init__(self, page: Page) -> None:
        self.page = page

    def open(self) -> None:
        self.page.goto(self.path)
