"""Page objects. Locators and user actions live here; assertions stay in tests."""

from pages.form_page import FormPage
from pages.items_page import ItemsPage
from pages.login_page import LoginPage

__all__ = ["FormPage", "ItemsPage", "LoginPage"]
