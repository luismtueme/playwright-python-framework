"""Time-dependent behavior, tested without waiting.

page.clock replaces the browser's timers, so 15 minutes pass in milliseconds.
"""

import pytest
from playwright.sync_api import Page, expect

from pages.items_page import ItemsPage
from tests.support import step


@pytest.fixture(autouse=True)
def _open_with_clock(page: Page, items_page: ItemsPage) -> None:
    page.clock.install(time="2026-01-05T09:00:00")
    items_page.open()
    expect(items_page.heading).to_be_visible()


def test_expires_after_15_minutes_without_activity(page: Page, items_page: ItemsPage) -> None:
    with step("one second before the timeout, the form is still usable"):
        page.clock.fast_forward("14:59")
        expect(items_page.session_expired).to_be_hidden()
        expect(items_page.name_input).to_be_visible()

    with step("at 15 minutes, the page asks to log in again"):
        page.clock.fast_forward("00:01")
        expect(items_page.session_expired).to_be_visible()
        expect(items_page.name_input).to_be_hidden()
        expect(items_page.log_in_again_link).to_have_attribute("href", "/login?next=/items")


def test_activity_restarts_the_timer(page: Page, items_page: ItemsPage) -> None:
    with step("10 minutes pass, then the user types"):
        page.clock.fast_forward("10:00")
        items_page.name_input.press("a")

    with step("10 more minutes: 20 in total, but only 10 idle"):
        page.clock.fast_forward("10:00")
        expect(items_page.session_expired).to_be_hidden()

    with step(f"{ItemsPage.idle_timeout} after the last keypress, it expires"):
        page.clock.fast_forward("05:00")
        expect(items_page.session_expired).to_be_visible()
