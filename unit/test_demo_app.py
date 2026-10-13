from datetime import UTC, datetime
from typing import Any

from demo_app.server import MemoryStore, MySqlStore, Request, create_app, start_demo_app
from utils.db_client import WriteResult


class FakeDb:
    def __init__(self) -> None:
        self.rows: dict[int, dict[str, Any]] = {}
        self.next_id = 1
        self.closed = False

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> WriteResult:
        if sql.strip().upper().startswith("INSERT"):
            name = params[0]
            item_id = self.next_id
            self.next_id += 1
            self.rows[item_id] = {"id": item_id, "name": name, "created_at": datetime(2026, 1, 5, tzinfo=UTC)}
            return WriteResult(insert_id=item_id, affected_rows=1)
        if sql.strip().upper().startswith("DELETE"):
            item_id = int(params[0])
            removed = self.rows.pop(item_id, None) is not None
            return WriteResult(insert_id=0, affected_rows=1 if removed else 0)
        return WriteResult(insert_id=0, affected_rows=0)

    def query(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        del sql, params
        return list(self.rows.values())

    def one(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> dict[str, Any] | None:
        del sql
        return self.rows.get(int(params[0]))

    def close(self) -> None:
        self.closed = True


def _request(method: str, path: str, body: bytes = b"", headers: dict[str, str] | None = None) -> Request:
    return Request(method, path, headers or {}, body)


def test_login_items_and_roles() -> None:
    app = create_app(MemoryStore())
    denied = app(_request("GET", "/api/items"))
    assert denied.status == 401

    login = app(_request("POST", "/api/login", b'{"username":"demo","password":"demo-password"}'))
    assert login.status == 200
    token = login.body["token"]
    headers = {"authorization": f"Bearer {token}"}
    me = app(_request("GET", "/api/me", headers=headers))
    assert me.body["role"] == "admin"

    created = app(_request("POST", "/api/items", b'{"name":"  Manhole 1  "}', headers))
    assert created.status == 201
    assert created.body["name"] == "Manhole 1"
    item_id = created.body["id"]

    listed = app(_request("GET", "/api/items", headers=headers))
    assert listed.body["items"][0]["id"] == item_id
    fetched = app(_request("GET", f"/api/items/{item_id}", headers=headers))
    assert fetched.status == 200
    deleted = app(_request("DELETE", f"/api/items/{item_id}", headers=headers))
    assert deleted.status == 204
    missing = app(_request("GET", f"/api/items/{item_id}", headers=headers))
    assert missing.status == 404


def test_viewer_cannot_change_items_and_validation_fails() -> None:
    app = create_app(MemoryStore())
    login = app(_request("POST", "/api/login", b'{"username":"viewer","password":"viewer-password"}'))
    headers = {"authorization": f"Bearer {login.body['token']}"}
    forbidden = app(_request("POST", "/api/items", b'{"name":"x"}', headers))
    assert forbidden.status == 403
    empty = app(_request("POST", "/api/login", b'{"username":"demo","password":"demo-password"}'))
    admin = {"authorization": f"Bearer {empty.body['token']}"}
    invalid = app(_request("POST", "/api/items", b'{"name":"  "}', admin))
    assert invalid.status == 400
    too_long = app(_request("POST", "/api/items", b'{"name":"' + b"x" * 256 + b'"}', admin))
    assert too_long.status == 400
    not_json = app(_request("POST", "/api/items", b"name=oops", admin))
    assert not_json.status == 400
    bad_login = app(_request("POST", "/api/login", b'{"username":"demo","password":"nope"}'))
    assert bad_login.status == 401


def test_pages_and_unknown_routes() -> None:
    app = create_app(MemoryStore())
    home = app(_request("GET", "/"))
    assert home.status == 200
    assert "Example Application" in home.body
    redirect = app(_request("GET", "/items"))
    assert redirect.status == 302
    assert redirect.headers["Location"] == "/login?next=%2Fitems"
    missing = app(_request("GET", "/nope"))
    assert missing.status == 404


def test_session_cookie_authenticates() -> None:
    app = create_app(MemoryStore())
    login = app(_request("POST", "/api/login", b'{"username":"demo","password":"demo-password"}'))
    cookie = login.headers["Set-Cookie"].split(";", 1)[0]
    me = app(_request("GET", "/api/me", headers={"cookie": cookie}))
    assert me.status == 200


def test_mysql_store_uses_the_injected_client() -> None:
    fake = FakeDb()
    store = MySqlStore(db=fake)  # type: ignore[arg-type]
    created = store.create("Culvert")
    assert created["name"] == "Culvert"
    fetched = store.get(created["id"])
    assert fetched is not None
    assert fetched["name"] == "Culvert"
    assert store.list()
    assert store.remove(created["id"]) is True
    assert store.get(created["id"]) is None
    store.close()
    assert fake.closed is True


def test_http_server_serves_the_home_page() -> None:
    demo = start_demo_app(port=0)
    try:
        import urllib.request

        with urllib.request.urlopen(demo.url, timeout=2) as response:
            body = response.read().decode("utf-8")
            status = response.status
        assert status == 200
        assert "Example Application" in body
    finally:
        demo.close()
