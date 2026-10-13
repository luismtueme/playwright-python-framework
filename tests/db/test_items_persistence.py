"""Checks what the API wrote, directly in MySQL.

Runs only when a database is configured (DB_HOST). expect_poll retries, so this
also works for apps that write asynchronously.
"""

from collections.abc import Callable
from typing import Any

import pytest

from config import config
from tests.support import expect_poll
from utils.api_client import ApiClient
from utils.db_client import DbClient

pytestmark = [
    pytest.mark.api,
    pytest.mark.db,
    pytest.mark.skipif(config.db is None, reason="No database configured: set DB_HOST (see .env.example)"),
]


def test_a_created_item_is_stored(
    authed_api: ApiClient, track_item: Callable[[dict[str, Any]], None], db: DbClient
) -> None:
    created = authed_api.post("/api/items", {"name": "Lateral 7 inspection"})
    assert created.status == 201
    assert isinstance(created.body, dict)
    track_item(created.body)
    expect_poll(
        lambda: db.one("SELECT id, name FROM items WHERE id = %s", [created.body["id"]]),
        message=f"row for item {created.body['id']}",
    ).to_equal({"id": created.body["id"], "name": "Lateral 7 inspection"})


def test_a_deleted_item_is_removed(
    authed_api: ApiClient,
    create_item: Callable[..., dict[str, Any]],
    db: DbClient,
) -> None:
    item = create_item("Temporary item")
    assert authed_api.delete(f"/api/items/{item['id']}").status == 204
    expect_poll(lambda: db.count("items", "id = %s", [item["id"]]), message=f"rows for item {item['id']}").to_be(0)
