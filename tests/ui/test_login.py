import re

import pytest
from playwright.sync_api import Page, expect

from config import Credentials
from pages.login_page import LoginPage
from tests.support import step

pytestmark = pytest.mark.role("anonymous")


@pytest.fixture(autouse=True)
def _open(login_page: LoginPage) -> None:
    login_page.open()


def test_has_the_expected_structure(page: Page) -> None:
    expect(page.get_by_role("main")).to_match_aria_snapshot(
        """
        - main:
          - heading "Log in" [level=1]
          - textbox "Username"
          - textbox "Password"
          - button "Log in"
        """
    )


@pytest.mark.smoke
def test_logs_in_with_the_configured_credentials(login_page: LoginPage, credentials: Credentials) -> None:
    with step("submit the configured credentials"):
        login_page.login(credentials.username, credentials.password)

    with step("the welcome message names the user"):
        expect(login_page.welcome).to_have_text(f"Welcome, {credentials.username}")


def test_rejects_a_wrong_password(login_page: LoginPage, credentials: Credentials) -> None:
    login_page.login(credentials.username, "not-the-password")
    expect(login_page.error).to_have_text("Invalid username or password")


def test_login_url_stays_on_the_login_page(page: Page) -> None:
    expect(page).to_have_url(re.compile(r"/login$"))
