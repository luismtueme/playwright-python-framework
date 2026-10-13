from collections.abc import Callable
from typing import Any

import pytest

from utils.api_client import ApiClient


@pytest.mark.smoke
def test_creates_an_item_and_fetches_it_by_id(
    authed_api: ApiClient, track_item: Callable[[dict[str, Any]], None]
) -> None:
    created = authed_api.post("/api/items", {"name": "Manhole 42 inspection"})
    assert created.status == 201
    assert isinstance(created.body, dict)
    track_item(created.body)
    assert isinstance(created.body["id"], int)
    assert created.body["name"] == "Manhole 42 inspection"

    fetched = authed_api.get(f"/api/items/{created.body['id']}")
    assert fetched.status == 200
    assert fetched.body == created.body


def test_rejects_an_item_without_a_name(authed_api: ApiClient) -> None:
    response = authed_api.post("/api/items", {"name": ""})
    assert response.status == 400
    assert response.body["error"]["code"] == "VALIDATION_ERROR"
    assert response.body["error"]["field"] == "name"


def test_rejects_a_body_that_is_not_json(authed_api: ApiClient) -> None:
    response = authed_api.post("/api/items", b"name=oops", headers={"Content-Type": "application/json"})
    assert response.status == 400
    assert response.body["error"]["code"] == "INVALID_JSON"


def test_rejects_a_name_longer_than_255_characters(authed_api: ApiClient) -> None:
    response = authed_api.post("/api/items", {"name": "x" * 256})
    assert response.status == 400
    assert response.body["error"]["code"] == "VALIDATION_ERROR"
    assert response.body["error"]["field"] == "name"


def test_rejects_requests_without_a_token(api: ApiClient) -> None:
    response = api.get("/api/items")
    assert response.status == 401


def test_deletes_an_item(authed_api: ApiClient, create_item: Callable[..., dict[str, Any]]) -> None:
    item = create_item()
    assert authed_api.delete(f"/api/items/{item['id']}").status == 204
    assert authed_api.get(f"/api/items/{item['id']}").status == 404
