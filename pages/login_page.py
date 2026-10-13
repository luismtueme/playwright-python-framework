"""Demo app login page ("/login")."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

from pages.base_page import BasePage


class LoginPage(BasePage):
    path = "/login"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.username: Locator = page.get_by_label("Username")
        self.password: Locator = page.get_by_label("Password")
        self.submit_button: Locator = page.get_by_role("button", name="Log in")
        self.error: Locator = page.get_by_role("alert")
        self.welcome: Locator = page.get_by_text(re.compile(r"^Welcome, "))

    def login(self, username: str, password: str) -> None:
        self.username.fill(username)
        self.password.fill(password)
        self.submit_button.click()
