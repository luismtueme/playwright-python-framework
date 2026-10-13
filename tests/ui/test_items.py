import re
from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Page, expect

from config import Credentials
from pages.items_page import ItemsPage
from pages.login_page import LoginPage
from tests.support import defined, expect_poll, step
from utils.api_client import ApiClient
from utils.test_data import Random


@pytest.mark.smoke
def test_opens_without_logging_in_again(items_page: ItemsPage, page: Page) -> None:
    items_page.open()
    expect(page).to_have_url(re.compile(r"/items$"))
    expect(items_page.heading).to_be_visible()


def test_has_the_expected_structure(items_page: ItemsPage, page: Page) -> None:
    items_page.open()
    expect(page.get_by_role("main")).to_match_aria_snapshot(
        """
        - main:
          - heading "Items" [level=1]
          - textbox "New item name"
          - button "Add item"
          - list "Items"
        """
    )


def test_lists_items_created_through_the_api(items_page: ItemsPage, create_item: Callable[..., dict[str, Any]]) -> None:
    item = create_item()
    items_page.open()
    expect(items_page.item(str(item["name"]))).to_be_visible()


def test_adds_an_item_through_the_ui(
    items_page: ItemsPage,
    authed_api: ApiClient,
    track_item: Callable[[dict[str, Any]], None],
    random: Random,
) -> None:
    name = f"UI item {random.int(1000, 9999)}"

    with step("add the item on the page"):
        items_page.open()
        created = defined(items_page.add_item(name), f'The app rejected "{name}"')
        track_item(created)

    with step("the list shows it"):
        expect(items_page.item(name)).to_be_visible()

    with step("the API returns it"):
        expect_poll(
            lambda: authed_api.get(f"/api/items/{created['id']}").body,
            message=f"item {created['id']} should be readable through the API",
        ).to_match({"name": name})


def test_rejects_an_empty_name(items_page: ItemsPage) -> None:
    items_page.open()
    assert items_page.add_item("") is None
    expect(items_page.error).to_have_text("Name is required")


@pytest.mark.role("anonymous")
def test_redirects_to_login_and_returns_after_logging_in(
    items_page: ItemsPage,
    login_page: LoginPage,
    page: Page,
    credentials: Credentials,
) -> None:
    items_page.open()
    expect(page).to_have_url(re.compile(r"/login\?next=%2Fitems$"))
    login_page.login(credentials.username, credentials.password)
    expect(page).to_have_url(re.compile(r"/items$"))
    expect(items_page.heading).to_be_visible()
