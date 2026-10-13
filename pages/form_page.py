"""Demo app form page ("/")."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from pages.base_page import BasePage


class FormPage(BasePage):
    path = "/"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.heading: Locator = page.get_by_role("heading", level=1)
        self.example_button: Locator = page.get_by_role("button", name="Run example action")
        self.result: Locator = page.get_by_text("Example action completed")
        self.input: Locator = page.get_by_label("Example input")
        self.submit_button: Locator = page.get_by_role("button", name="Submit")
        self.message: Locator = page.get_by_role("status")

    def run_example_action(self) -> None:
        self.example_button.click()

    def submit(self, value: str) -> None:
        self.input.fill(value)
        self.submit_button.click()
