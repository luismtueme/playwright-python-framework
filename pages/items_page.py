"""Demo app items page ("/items"). Requires a logged-in session."""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Locator, Page

from pages.base_page import BasePage


class ItemsPage(BasePage):
    path = "/items"
    idle_timeout = "15:00"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.heading: Locator = page.get_by_role("heading", name="Items")
        self.name_input: Locator = page.get_by_label("New item name")
        self.add_button: Locator = page.get_by_role("button", name="Add item")
        self.error: Locator = page.get_by_role("alert")
        self.list: Locator = page.get_by_role("list", name="Items")
        self.session_expired: Locator = page.get_by_text("Your session has expired")
        self.log_in_again_link: Locator = page.get_by_role("link", name="Log in again")
        self.read_only_notice: Locator = page.get_by_text("You have read-only access")
        self.loading: Locator = page.get_by_text("Loading items…")
        self.load_error: Locator = page.get_by_text("Could not load the items.")
        self.retry_button: Locator = page.get_by_role("button", name="Try again")

    def item(self, name: str) -> Locator:
        """List entry for an item, located by its visible name."""
        return self.list.get_by_role("listitem").filter(has_text=name)

    def add_item(self, name: str) -> dict[str, Any] | None:
        """Add an item through the UI. Returns the created item, or None if the app rejected it."""
        self.name_input.fill(name)
        with self.page.expect_response(
            lambda response: response.url.endswith("/api/items") and response.request.method == "POST"
        ) as waited:
            self.add_button.click()
        response = waited.value
        if not response.ok:
            return None
        body = response.json()
        return body if isinstance(body, dict) else None
