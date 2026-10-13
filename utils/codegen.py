"""Open Playwright's code generator already logged in.

    uv run python -m utils.codegen
    uv run python -m utils.codegen /items --role viewer
    uv run python -m utils.codegen --print

Starts the demo app when it is the target and isn't running. Paste the recorded
steps into a test and move the locators into a page object (see AGENTS.md).
"""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request

from config import ROLES, Role, app_url, config, require_credentials
from demo_app.server import DemoApp, start_demo_app
from utils.auth_state import auth_file
from utils.scaffold import parse_args


def _is_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return int(response.status) < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def _save_session(base_url: str, role: Role) -> tuple[str, str]:
    from playwright.sync_api import sync_playwright

    credentials = require_credentials(config, role)
    with sync_playwright() as playwright:
        context = playwright.request.new_context(base_url=base_url)
        try:
            login = context.post(
                "/api/login", data={"username": credentials.username, "password": credentials.password}
            )
            if not login.ok:
                raise RuntimeError(f"Login as {role} failed ({login.status}): {login.text()}")
            me = context.get("/api/me")
            body = me.json()
            user = body.get("username") if isinstance(body, dict) else role
            destination = auth_file(role)
            context.storage_state(path=destination)
            return destination, str(user)
        finally:
            context.dispose()


def main() -> int:
    name, options = parse_args(sys.argv[1:])
    url_path = name or "/"
    role_value = options.get("role") if isinstance(options.get("role"), str) else "admin"
    if role_value not in ROLES:
        print(f"--role must be one of: {', '.join(ROLES)}", file=sys.stderr)
        return 1
    role: Role = role_value
    base_url = app_url(config)
    server: DemoApp | None = None
    if config.use_demo_app and not _is_up(base_url):
        server = start_demo_app()
        base_url = server.url
    try:
        storage, user = _save_session(base_url, role)
        target = base_url.rstrip("/") + (url_path if url_path.startswith("/") else f"/{url_path}")
        args = ["playwright", "codegen", f"--load-storage={storage}", target]
        print(f"Logged in as {user} ({role})")
        if options.get("print"):
            print("uv run " + " ".join(args))
            return 0
        completed = subprocess.run(["uv", "run", *args], check=False)
        return completed.returncode
    finally:
        if server is not None:
            server.close()


if __name__ == "__main__":
    raise SystemExit(main())
