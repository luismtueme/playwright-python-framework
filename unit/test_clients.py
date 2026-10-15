from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import pymysql
import pytest

from demo_app.server import start_demo_app
from utils.api_client import ApiClient, redact
from utils.db_client import DbClient


def _using_playwright(check: Callable[[Any], None]) -> None:
    """Run sync Playwright on a thread that has no asyncio loop.

    The suite session already owns a sync driver. A second sync_playwright()
    on that thread raises "Sync API inside the asyncio loop".
    """
    from playwright.sync_api import sync_playwright

    errors: list[Exception] = []

    def target() -> None:
        try:
            with sync_playwright() as playwright:
                check(playwright)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]


def test_redact_masks_secrets_and_keeps_other_fields() -> None:
    masked = redact({"password": "secret", "name": "Manhole", "nested": [{"api_key": "k"}]})
    assert masked == {"password": "***", "name": "Manhole", "nested": [{"api_key": "***"}]}


def test_api_client_logs_in_and_creates_an_item() -> None:
    demo = start_demo_app(port=0)

    def check(playwright: Any) -> None:
        client = ApiClient.create(playwright, base_url=demo.url)
        try:
            logged_in = client.login("demo", "demo-password")
            assert logged_in.status == 200
            created = client.post("/api/items", {"name": "Lateral 3 cleaning"})
            assert created.status == 201
            assert created.body["name"] == "Lateral 3 cleaning"
        finally:
            client.dispose()

    try:
        _using_playwright(check)
    finally:
        demo.close()


def test_api_client_reports_a_failed_login() -> None:
    demo = start_demo_app(port=0)

    def check(playwright: Any) -> None:
        client = ApiClient.create(playwright, base_url=demo.url)
        try:
            with pytest.raises(RuntimeError, match="Login failed"):
                client.login("demo", "nope")
        finally:
            client.dispose()

    try:
        _using_playwright(check)
    finally:
        demo.close()


class _Cursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.lastrowid = 5
        self.rowcount = 1

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, params: Any = ()) -> None:
        self.sql = sql
        self.params = params

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.closed = False

    def cursor(self) -> _Cursor:
        return _Cursor(self._rows)

    def close(self) -> None:
        self.closed = True


def test_db_client_queries_and_rejects_bad_table_names(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _Connection([{"id": 1, "total": 4}])

    def connect(**kwargs: Any) -> _Connection:
        assert kwargs["host"] == "localhost"
        return connection

    monkeypatch.setattr(pymysql, "connect", connect)
    from config import DbConfig

    client = DbClient(DbConfig(host="localhost", port=3306, user="u", password="p", database="d"))
    assert client.one("SELECT id FROM items WHERE id = %s", [1]) == {"id": 1, "total": 4}
    assert client.count("items", "id = %s", [1]) == 4
    written = client.execute("INSERT INTO items (name) VALUES (%s)", ["x"])
    assert written.insert_id == 5
    client.close()
    with pytest.raises(ValueError, match="Invalid table name"):
        client.count("items;drop")


def test_db_client_requires_configuration() -> None:
    with pytest.raises(RuntimeError, match="DB_HOST"):
        DbClient(None)
