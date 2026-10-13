"""Permissions matrix: every role against every API action.

One test per cell, so a failure names the exact role and action.
"""

from collections.abc import Callable
from typing import Any

import pytest

from config import Role
from utils.api_client import ApiClient
from utils.test_data import Random

type Actor = Role | Any
type Action = str

MATRIX: dict[str, dict[str, int]] = {
    "admin": {"list items": 200, "read an item": 200, "create an item": 201, "delete an item": 204},
    "viewer": {"list items": 200, "read an item": 200, "create an item": 403, "delete an item": 403},
    "anonymous": {"list items": 401, "read an item": 401, "create an item": 401, "delete an item": 401},
}

pytestmark = pytest.mark.api


def _act(
    action: str,
    api: ApiClient,
    item_id: int,
    track_item: Callable[[dict[str, Any]], None],
    random: Random,
) -> int:
    if action == "list items":
        return api.get("/api/items").status
    if action == "read an item":
        return api.get(f"/api/items/{item_id}").status
    if action == "create an item":
        response = api.post("/api/items", {"name": f"Permission check {random.int(1, 9999)}"})
        if response.status == 201 and isinstance(response.body, dict):
            track_item(response.body)
        return response.status
    return api.delete(f"/api/items/{item_id}").status


@pytest.mark.parametrize("actor", list(MATRIX))
@pytest.mark.parametrize("action", list(MATRIX["admin"]))
def test_permission(
    actor: str,
    action: str,
    api: ApiClient,
    api_as: Callable[[Role], ApiClient],
    create_item: Callable[..., dict[str, Any]],
    track_item: Callable[[dict[str, Any]], None],
    random: Random,
) -> None:
    status = MATRIX[actor][action]
    item = create_item()
    client = api if actor == "anonymous" else api_as(actor)  # type: ignore[arg-type]
    assert _act(action, client, int(item["id"]), track_item, random) == status
