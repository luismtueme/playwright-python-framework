from collections.abc import Callable

import pytest
from playwright.sync_api import expect

from pages.form_page import FormPage
from pages.items_page import ItemsPage
from pages.login_page import LoginPage

# END_A11Y_IMPORTS

CheckAccessibility = Callable[..., None]

pytestmark = pytest.mark.a11y


def test_form_page(form_page: FormPage, check_accessibility: CheckAccessibility) -> None:
    form_page.open()
    check_accessibility()


def test_items_page(items_page: ItemsPage, check_accessibility: CheckAccessibility) -> None:
    items_page.open()
    expect(items_page.heading).to_be_visible()
    check_accessibility()


# LOGGED_OUT_A11Y
@pytest.mark.role("anonymous")
def test_login_page(login_page: LoginPage, check_accessibility: CheckAccessibility) -> None:
    login_page.open()
    check_accessibility()
