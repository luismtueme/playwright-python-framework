import pytest
from playwright.sync_api import Page, expect

from pages.form_page import FormPage
from pages.items_page import ItemsPage
from pages.login_page import LoginPage
from utils.screenshots import expect_screenshot

pytestmark = pytest.mark.visual


def test_form_page(form_page: FormPage, page: Page) -> None:
    form_page.open()
    expect_screenshot(page, "form-page.png", full_page=True)


def test_form_page_with_a_validation_message(form_page: FormPage, page: Page) -> None:
    form_page.open()
    form_page.submit("")
    expect(form_page.message).to_have_text("Please enter a value")
    expect_screenshot(page, "form-page-validation.png", full_page=True)


def test_items_page(items_page: ItemsPage, page: Page) -> None:
    items_page.open()
    expect(items_page.heading).to_be_visible()
    expect_screenshot(page, "items-page.png", full_page=True, mask=[items_page.list])


@pytest.mark.role("anonymous")
def test_login_page_with_an_error(login_page: LoginPage, page: Page) -> None:
    login_page.open()
    login_page.login("demo", "not-the-password")
    expect(login_page.error).to_have_text("Invalid username or password")
    expect_screenshot(page, "login-page-error.png", full_page=True)
