"""How the UI behaves when the network or the server fails.

page.route intercepts the page's API calls, so each failure is exact and repeatable.
"""

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Page, Route, expect

from pages.items_page import ItemsPage
from tests.support import step

pytestmark = pytest.mark.contract(False)


def test_a_server_error_shows_a_message_and_retry_recovers(
    page: Page,
    items_page: ItemsPage,
    create_item: Callable[..., dict[str, Any]],
) -> None:
    item = create_item()
    page.route("**/api/items", lambda route: route.fulfill(status=500, json={"error": {"code": "SERVER_ERROR"}}))

    with step("the failed load shows an error with a retry button"):
        items_page.open()
        expect(items_page.load_error).to_be_visible()
        expect(items_page.retry_button).to_be_visible()

    with step("once the API is back, retry shows the list"):
        page.unroute("**/api/items")
        items_page.retry_button.click()
        expect(items_page.load_error).to_be_hidden()
        expect(items_page.item(str(item["name"]))).to_be_visible()


def test_a_dropped_connection_shows_the_same_message(page: Page, items_page: ItemsPage) -> None:
    page.route("**/api/items", lambda route: route.abort("connectionreset"))
    items_page.open()
    expect(items_page.load_error).to_be_visible()


def test_a_slow_response_shows_a_loading_indicator(
    page: Page,
    items_page: ItemsPage,
    create_item: Callable[..., dict[str, Any]],
) -> None:
    item = create_item()
    paused: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method == "GET":
            paused.append(route)
            return
        route.continue_()

    page.route("**/api/items", hold)
    items_page.open()
    expect(items_page.loading).to_be_visible()
    assert paused, "the list request was not held"
    paused.pop().continue_()
    expect(items_page.loading).to_be_hidden()
    expect(items_page.item(str(item["name"]))).to_be_visible()


def test_a_failed_save_keeps_the_text_and_shows_a_message(page: Page, items_page: ItemsPage) -> None:
    items_page.open()
    expect(items_page.loading).to_be_hidden()

    def fail_post(route: Route) -> None:
        if route.request.method == "POST":
            route.fulfill(status=503, json={"error": {"code": "SERVER_ERROR", "message": "db pool exhausted"}})
        else:
            route.continue_()

    page.route("**/api/items", fail_post)
    items_page.name_input.fill("Culvert 9 cleaning")
    items_page.add_button.click()
    expect(items_page.error).to_have_text("Could not save the item. Try again.")
    expect(items_page.name_input).to_have_value("Culvert 9 cleaning")
    expect(items_page.item("Culvert 9 cleaning")).to_have_count(0)
