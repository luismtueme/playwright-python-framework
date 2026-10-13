"""Demo application under test.

A small web app and JSON API so the example tests have a deterministic target.
Point BASE_URL at your real application and delete this package when you adopt
the framework.

    Pages:  /            form page
            /login       login page (?next=/items returns there after login)
            /items       items page, requires a session (redirects to /login)
    API:    POST   /api/login        { username, password } -> { token, user }, also sets a session cookie
            GET    /api/me           (auth) { username, role }
            GET    /api/items        (auth) list items
            POST   /api/items        (admin) { name } -> item
            GET    /api/items/:id    (auth)
            DELETE /api/items/:id    (admin)

Roles: admin (demo / demo-password) can do everything; viewer (viewer /
viewer-password) can read, and gets 403 on changes.
API routes accept either "Authorization: Bearer <token>" or the session cookie.
Items are kept in memory, or in MySQL when DB_HOST is set (table `items`).

Run standalone: uv run python -m demo_app  (port: DEMO_APP_PORT, default 4173)
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

from config import DEMO_USERS, ROLES, DbConfig, Role, config
from utils.db_client import DbClient

PUBLIC_DIR = Path(__file__).resolve().parent / "public"
PAGES = {"/": "index.html", "/login": "login.html", "/items": "items.html"}
PROTECTED_PAGES = {"/items"}
SESSION_COOKIE = "session"
MAX_NAME_LENGTH = 255
FORBIDDEN = {"error": {"code": "FORBIDDEN", "message": "Your role cannot do this"}}


class HttpError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class Response:
    status: int
    body: Any
    headers: dict[str, str]


class Store(Protocol):
    def list(self) -> list[dict[str, Any]]: ...
    def create(self, name: str) -> dict[str, Any]: ...
    def get(self, item_id: int) -> dict[str, Any] | None: ...
    def remove(self, item_id: int) -> bool: ...
    def close(self) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._items.values())

    def create(self, name: str) -> dict[str, Any]:
        with self._lock:
            item_id = self._next_id
            item: dict[str, Any] = {"id": item_id, "name": name, "createdAt": _now()}
            self._next_id += 1
            self._items[item_id] = item
            return item

    def get(self, item_id: int) -> dict[str, Any] | None:
        with self._lock:
            return self._items.get(item_id)

    def remove(self, item_id: int) -> bool:
        with self._lock:
            return self._items.pop(item_id, None) is not None

    def close(self) -> None:
        return None


class MySqlStore:
    def __init__(self, db_config: DbConfig | None = None, db: DbClient | None = None) -> None:
        self._db = db if db is not None else DbClient(db_config)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
            )
            """
        )

    def list(self) -> list[dict[str, Any]]:
        return [_to_item(row) for row in self._db.query("SELECT * FROM items ORDER BY id")]

    def create(self, name: str) -> dict[str, Any]:
        result = self._db.execute("INSERT INTO items (name) VALUES (%s)", [name])
        row = self._db.one("SELECT * FROM items WHERE id = %s", [result.insert_id])
        if row is None:
            raise RuntimeError(f"Item {result.insert_id} was not saved")
        return _to_item(row)

    def get(self, item_id: int) -> dict[str, Any] | None:
        row = self._db.one("SELECT * FROM items WHERE id = %s", [item_id])
        return _to_item(row) if row else None

    def remove(self, item_id: int) -> bool:
        result = self._db.execute("DELETE FROM items WHERE id = %s", [item_id])
        return result.affected_rows > 0

    def close(self) -> None:
        self._db.close()


def _to_item(row: dict[str, Any]) -> dict[str, Any]:
    created = row["created_at"]
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        created_at = created.astimezone(UTC).isoformat().replace("+00:00", "Z")
    else:
        created_at = str(created)
    return {"id": int(row["id"]), "name": row["name"], "createdAt": created_at}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def session_token(headers: dict[str, str]) -> str:
    authorization = headers.get("authorization", "")
    match = re.match(r"^Bearer (.+)$", authorization)
    if match:
        return match.group(1)
    cookie = headers.get("cookie", "")
    for part in cookie.split(";"):
        piece = part.strip()
        if piece.startswith(f"{SESSION_COOKIE}="):
            return piece[len(SESSION_COOKIE) + 1 :]
    return ""


def create_app(store: Store) -> Callable[[Request], Response]:
    sessions: dict[str, dict[str, str]] = {}
    lock = threading.Lock()

    def handle(request: Request) -> Response:
        with lock:
            return _handle(request, sessions, store)

    return handle


def _handle(request: Request, sessions: dict[str, dict[str, str]], store: Store) -> Response:
    path = urlsplit(request.path).path
    session = sessions.get(session_token(request.headers))
    try:
        page = PAGES.get(path)
        if request.method == "GET" and page:
            if path in PROTECTED_PAGES and session is None:
                return Response(302, "", {"Location": f"/login?next={quote(path, safe='')}"})
            return Response(
                200, (PUBLIC_DIR / page).read_text(encoding="utf-8"), {"Content-Type": "text/html; charset=utf-8"}
            )

        if request.method == "POST" and path == "/api/login":
            payload = _read_json(request.body)
            username = payload.get("username")
            password = payload.get("password")
            role = _matching_role(username, password)
            if role is None or not isinstance(username, str):
                return _json(401, {"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid username or password"}})
            token = str(uuid.uuid4())
            sessions[token] = {"username": username, "role": role}
            return _json(
                200,
                {"token": token, "user": {"username": username, "role": role}},
                {"Set-Cookie": f"{SESSION_COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/"},
            )

        if path == "/api/me" or path.startswith("/api/items"):
            if session is None:
                return _json(401, {"error": {"code": "UNAUTHORIZED", "message": "Missing or invalid token"}})
            if path == "/api/me" and request.method == "GET":
                return _json(200, session)
            item_id = _item_id(path)
            is_change = request.method in {"POST", "DELETE"}
            if is_change and session["role"] != "admin":
                return _json(403, FORBIDDEN)
            if path == "/api/items" and request.method == "GET":
                return _json(200, {"items": store.list()})
            if path == "/api/items" and request.method == "POST":
                return _create_item(_read_json(request.body), store)
            if item_id is not None and request.method == "GET":
                item = store.get(item_id)
                return _json(200, item) if item else _json(404, {"error": {"code": "NOT_FOUND"}})
            if item_id is not None and request.method == "DELETE":
                return Response(204, "", {}) if store.remove(item_id) else _json(404, {"error": {"code": "NOT_FOUND"}})

        return _json(404, {"error": {"code": "NOT_FOUND"}})
    except HttpError as caught:
        return _json(caught.status, {"error": {"code": caught.code, "message": caught.args[0]}})
    except Exception as caught:
        return _json(500, {"error": {"code": "SERVER_ERROR", "message": str(caught)}})


def _matching_role(username: object, password: object) -> Role | None:
    for role in ROLES:
        user = DEMO_USERS[role]
        if user.username == username and user.password == password:
            return role
    return None


def _item_id(path: str) -> int | None:
    match = re.fullmatch(r"/api/items/(\d+)", path)
    if not match:
        return None
    return int(match.group(1))


def _create_item(payload: dict[str, Any], store: Store) -> Response:
    name = payload.get("name")
    trimmed = name.strip() if isinstance(name, str) else ""
    if trimmed == "":
        return _json(400, {"error": {"code": "VALIDATION_ERROR", "field": "name", "message": "Name is required"}})
    if len(trimmed) > MAX_NAME_LENGTH:
        return _json(
            400,
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "field": "name",
                    "message": f"Name must be {MAX_NAME_LENGTH} characters or fewer",
                }
            },
        )
    return _json(201, store.create(trimmed))


def _read_json(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as caught:
        raise HttpError(400, "INVALID_JSON", "Invalid JSON body") from caught
    if not isinstance(parsed, dict):
        raise HttpError(400, "INVALID_JSON", "Invalid JSON body")
    return parsed


def _json(status: int, body: Any, headers: dict[str, str] | None = None) -> Response:
    extra = {"Content-Type": "application/json; charset=utf-8"}
    extra.update(headers or {})
    return Response(status, body, extra)


class DemoApp:
    def __init__(self, url: str, close: Callable[[], None]) -> None:
        self.url = url
        self._close = close

    def close(self) -> None:
        self._close()


class _Handler(BaseHTTPRequestHandler):
    server: AppServer

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def log_message(self, format: str, *args: Any) -> None:
        return None

    def _dispatch(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        headers = {key.lower(): value for key, value in self.headers.items()}
        response = self.server.app(Request(self.command, self.path, headers, body))
        payload = b""
        if response.status != 204:
            if isinstance(response.body, str):
                payload = response.body.encode("utf-8")
            elif response.body is not None:
                payload = json.dumps(response.body).encode("utf-8")
        self.send_response(response.status)
        for key, value in response.headers.items():
            self.send_header(key, value)
        if payload and "Content-Type" not in response.headers and isinstance(response.body, str):
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)


class AppServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], app: Callable[[Request], Response]) -> None:
        super().__init__(address, _Handler)
        self.app = app


def start_demo_app(port: int | None = None, host: str = "127.0.0.1") -> DemoApp:
    """Start the demo app. Port 0 picks a free port (used by the unit tests)."""
    store: Store = MySqlStore(config.db) if config.db else MemoryStore()
    app = create_app(store)
    server = AppServer((host, config.demo_app_port if port is None else port), app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bound_host, bound_port = server.server_address[:2]
    host_name = bound_host.decode() if isinstance(bound_host, bytes) else str(bound_host)
    _wait_until_listening(f"http://{host_name}:{bound_port}/")

    def close() -> None:
        server.shutdown()
        server.server_close()
        store.close()
        thread.join(timeout=5)

    return DemoApp(url=f"http://{host_name}:{bound_port}", close=close)


def _wait_until_listening(url: str) -> None:
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.2) as response:
                if response.status < 500:
                    return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"Demo app did not start at {url}")


def main() -> None:
    app = start_demo_app()
    print(f"Demo app running at {app.url}", flush=True)
    threading.Event().wait()
