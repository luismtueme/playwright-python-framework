"""Without a viewport meta tag, phones lay pages out 980px wide and shrink them.

Runs on every PR. The nightly job repeats the whole suite on device profiles.
"""

import pytest
from playwright.sync_api import Page, expect

from pages.form_page import FormPage
from pages.items_page import ItemsPage
from pages.login_page import LoginPage

PHONE = {"width": 390, "height": 844}
pytestmark = pytest.mark.phone


@pytest.fixture(autouse=True)
def _skip_firefox(browser_name: str) -> None:
    if browser_name == "firefox":
        pytest.skip("Firefox has no mobile emulation")


def _expect_fits_phone(page: Page) -> None:
    layout = page.evaluate("() => ({ width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth })")
    assert layout["width"] == PHONE["width"], "lays out at the device width, not a zoomed-out desktop width"
    assert layout["scrollWidth"] <= PHONE["width"], "no horizontal scrolling"


def test_the_form_page_fits_the_screen(form_page: FormPage, page: Page) -> None:
    form_page.open()
    expect(form_page.heading).to_be_visible()
    _expect_fits_phone(page)


def test_the_items_page_fits_the_screen(items_page: ItemsPage, page: Page) -> None:
    items_page.open()
    expect(items_page.heading).to_be_visible()
    _expect_fits_phone(page)


@pytest.mark.role("anonymous")
def test_the_login_page_fits_the_screen(login_page: LoginPage, page: Page) -> None:
    login_page.open()
    expect(login_page.submit_button).to_be_visible()
    _expect_fits_phone(page)
