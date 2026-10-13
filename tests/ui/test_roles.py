"""What each role sees in the UI. The API side is tests/api/test_permissions.py."""

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import expect

from pages.items_page import ItemsPage


@pytest.mark.role("admin")
def test_admin_sees_the_add_form(items_page: ItemsPage) -> None:
    items_page.open()
    expect(items_page.name_input).to_be_visible()
    expect(items_page.read_only_notice).to_be_hidden()


@pytest.mark.role("viewer")
def test_viewer_lists_items_but_hides_the_add_form(
    items_page: ItemsPage, create_item: Callable[..., dict[str, Any]]
) -> None:
    item = create_item()
    items_page.open()
    expect(items_page.read_only_notice).to_be_visible()
    expect(items_page.name_input).to_be_hidden()
    expect(items_page.item(str(item["name"]))).to_be_visible()
