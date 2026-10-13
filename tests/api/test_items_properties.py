"""Generated-input tests. A failure is shrunk, and TEST_SEED reproduces it."""

from collections.abc import Callable
from typing import Any

import hypothesis.strategies as st
import pytest

from utils.api_client import ApiClient

MAX_NAME_LENGTH = 255
pytestmark = pytest.mark.api

_NAMES = st.one_of(
    st.text(max_size=40),
    st.binary(max_size=40).map(lambda raw: raw.decode("utf-8", errors="replace")),
    st.tuples(st.sampled_from([" ", "\t", "\n", "\u00a0", "\u3000"]), st.text(max_size=20)).map(
        lambda pair: pair[0] + pair[1] + pair[0]
    ),
    st.sampled_from(["", " ", "\t\n"]),
    st.integers(min_value=MAX_NAME_LENGTH - 2, max_value=MAX_NAME_LENGTH + 3).map(lambda count: "é" * count),
    st.integers(min_value=MAX_NAME_LENGTH - 2, max_value=MAX_NAME_LENGTH + 3).map(lambda count: "🧪" * count),
)


def _valid(name: str) -> bool:
    length = len(name.strip())
    return 1 <= length <= MAX_NAME_LENGTH


def _check(api: ApiClient, track_item: Callable[[dict[str, Any]], None], name: str) -> None:
    response = api.post("/api/items", {"name": name})
    if not _valid(name):
        assert response.status == 400, f"invalid name {name!r} should be rejected"
        return
    assert response.status == 201, f"valid name {name!r} should be accepted"
    assert isinstance(response.body, dict)
    track_item(response.body)
    assert response.body["name"] == name.strip()
    fetched = api.get(f"/api/items/{response.body['id']}")
    assert isinstance(fetched.body, dict)
    assert fetched.body["name"] == name.strip()


def test_any_name_is_saved_trimmed_or_rejected(
    authed_api: ApiClient,
    track_item: Callable[[dict[str, Any]], None],
    check_property: Callable[..., None],
) -> None:
    check_property(_NAMES, lambda name: _check(authed_api, track_item, name))
