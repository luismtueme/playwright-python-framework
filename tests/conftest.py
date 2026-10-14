"""Custom pytest fixtures. Tests get page objects, API clients, and test data from here.

Browser tests start logged in as admin. Pick another role per test or module:

    pytestmark = pytest.mark.role("viewer")
    pytestmark = pytest.mark.role("anonymous")

Every API response is checked against the OpenAPI contract. Turn that off only
for tests that fake responses:

    pytestmark = pytest.mark.contract(False)
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from hypothesis import HealthCheck, given, seed, settings
from playwright.sync_api import Page, Playwright, expect

from config import ROOT, Role, app_url, require_credentials
from config import config as app_config
from demo_app.server import DemoApp, start_demo_app
from pages.form_page import FormPage
from pages.items_page import ItemsPage
from pages.login_page import LoginPage

# END_PAGE_IMPORTS
from utils.accessibility import find_accessibility_violations, format_violations
from utils.api_client import ApiClient
from utils.contract import Contract, ContractResponse, ContractViolation
from utils.db_client import DbClient
from utils.test_data import RUN_SEED, Random, item_name, seed_for

_demo: DemoApp | None = None
_started = time.monotonic()

CheckAccessibility = Callable[..., None]
PHONE = {"width": 390, "height": 844}


def pytest_load_initial_conftests(early_config: pytest.Config, parser: pytest.Parser, args: list[str]) -> None:
    del early_config, parser
    if _unit_only(args):
        return
    _append(args, "--base-url", app_url(app_config))
    if not _has_option(args, "--browser"):
        args.extend(["--browser", app_config.browser])
    if app_config.device and not _has_option(args, "--device"):
        args.extend(["--device", app_config.device])
    if not app_config.headless and "--headed" not in args:
        args.append("--headed")
    _append(args, "--tracing", app_config.trace)
    _append(args, "--video", app_config.video)
    _append(args, "--screenshot", "only-on-failure")
    if app_config.retries and not _has_option(args, "--reruns"):
        args.extend(["--reruns", str(app_config.retries)])
    if app_config.workers > 1 and not _has_option(args, "-n") and not _has_option(args, "--numprocesses"):
        args.extend(["-n", str(app_config.workers)])
    if not _has_option(args, "--timeout"):
        args.extend(["--timeout", str(max(1, app_config.timeouts.test // 1000)), "--timeout-method", "thread"])
    if not _has_option(args, "--output"):
        args.extend(["--output", "test-results"])


def pytest_configure(config: pytest.Config) -> None:
    global _demo
    expect.set_options(timeout=app_config.timeouts.expect)
    if not config.option.markexpr:
        suite = os.environ.get("PW_SUITE", "default")
        if suite == "quarantine":
            config.option.markexpr = "quarantine"
        elif suite == "visual":
            config.option.markexpr = "visual"
        elif suite != "all":
            config.option.markexpr = "not quarantine and not visual"
    if getattr(config, "workerinput", None) is not None or _unit_only(config.args):
        return
    if app_config.use_demo_app and _demo is None:
        _demo = start_demo_app()


def pytest_unconfigure(config: pytest.Config) -> None:
    global _demo
    if getattr(config, "workerinput", None) is not None:
        return
    if _demo is not None:
        _demo.close()
        _demo = None
    _write_report(config)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = str(getattr(item, "fspath", ""))
        if "/tests/api/" in path.replace("\\", "/") or path.endswith("test_permissions.py"):
            item.add_marker(pytest.mark.api)


@pytest.fixture(scope="session")
def base_url() -> str:
    return app_url(app_config)


@pytest.fixture(scope="session")
def api_contract() -> Contract | None:
    if not app_config.open_api_spec:
        return None
    return Contract(app_config.open_api_spec)


@pytest.fixture(scope="session")
def auth_states(playwright: Playwright, base_url: str) -> dict[str, Any]:
    states: dict[str, Any] = {}
    for role in ("admin", "viewer"):
        context = playwright.request.new_context(base_url=base_url)
        try:
            credentials = require_credentials(app_config, role)
            response = context.post(
                "/api/login", data={"username": credentials.username, "password": credentials.password}
            )
            if response.status != 200:
                raise RuntimeError(f"Login as {role} failed ({response.status}): {response.text()}")
            states[role] = context.storage_state()
        finally:
            context.dispose()
    return states


@pytest.fixture
def browser_context_args(
    pytestconfig: pytest.Config,
    playwright: Playwright,
    device: str | None,
    base_url: str | None,
    _pw_artifacts_folder: Any,
    request: pytest.FixtureRequest,
    auth_states: dict[str, Any],
    browser_name: str,
) -> dict[str, Any]:
    # pytest-playwright's --device flag is the override. TEST_DEVICE is the
    # fallback: pytest does not call pytest_load_initial_conftests from a
    # conftest, so the early hook cannot inject --device on its own.
    selected_device = device or app_config.device
    context_args: dict[str, Any] = {}
    if selected_device:
        context_args.update(playwright.devices[selected_device])
    if base_url:
        context_args["base_url"] = base_url
    video_option = pytestconfig.getoption("--video")
    if video_option in {"on", "retain-on-failure"}:
        context_args["record_video_dir"] = _pw_artifacts_folder.name
    role = _role(request)
    if role == "anonymous":
        context_args["storage_state"] = {"cookies": [], "origins": []}
    else:
        context_args["storage_state"] = auth_states[role]
    if not selected_device:
        context_args["viewport"] = {"width": app_config.viewport.width, "height": app_config.viewport.height}
    if request.node.get_closest_marker("phone"):
        context_args["viewport"] = PHONE
        if browser_name != "firefox":
            context_args["is_mobile"] = True
            context_args["has_touch"] = True
    return context_args


@pytest.fixture
def credentials(request: pytest.FixtureRequest) -> Any:
    role = _role(request)
    selected: Role = "admin" if role == "anonymous" else cast(Role, role)
    return require_credentials(app_config, selected)


@pytest.fixture
def random(request: pytest.FixtureRequest) -> Random:
    test_seed = seed_for(request.node.nodeid)
    request.node.user_properties.append(("seed", f"TEST_SEED={RUN_SEED} (test seed {test_seed})"))
    return Random(test_seed)


@pytest.fixture
def form_page(page: Page) -> FormPage:
    return FormPage(page)


@pytest.fixture
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture
def items_page(page: Page) -> ItemsPage:
    return ItemsPage(page)


# END_PAGE_FIXTURES


@pytest.fixture(autouse=True)
def _page_contract(request: pytest.FixtureRequest) -> Any:
    if "page" not in request.fixturenames:
        yield
        return
    page = request.getfixturevalue("page")
    page.set_default_timeout(app_config.timeouts.action)
    page.set_default_navigation_timeout(app_config.timeouts.navigation)
    contract: Contract | None = request.getfixturevalue("api_contract")
    problems: list[str] = []
    if contract is not None and _contract_enabled(request):

        def on_response(response: Any) -> None:
            path = urlsplit(response.url).path
            if not path.startswith("/api/"):
                return
            try:
                text = response.text()
                unavailable = False
            except Exception:
                text = ""
                unavailable = True
            body: Any = text or None
            if text:
                try:
                    body = json.loads(text)
                except json.JSONDecodeError:
                    body = text
            problems.extend(
                contract.check(
                    ContractResponse(
                        method=response.request.method,
                        path=path,
                        status=response.status,
                        body=body,
                        body_unavailable=unavailable,
                    )
                )
            )

        page.on("response", on_response)
    yield
    if problems:
        raise ContractViolation(problems)


@pytest.fixture
def check_accessibility(page: Page, output_path: str) -> CheckAccessibility:
    def check(*, exclude: list[str] | None = None, disable_rules: list[str] | None = None) -> None:
        violations = find_accessibility_violations(page, exclude=exclude, disable_rules=disable_rules)
        destination = Path(output_path) / "accessibility-violations.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(violations, indent=2), encoding="utf-8")
        assert violations == [], format_violations(violations)

    return check


@pytest.fixture
def check_property(random: Random) -> Callable[..., None]:
    def run(strategy: Any, rule: Callable[[Any], None], runs: int = 80) -> None:
        @seed(random.seed)
        @settings(
            max_examples=runs,
            database=None,
            deadline=None,
            suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
        )
        @given(strategy)
        def _check(value: Any) -> None:
            rule(value)

        _check()

    return run


@pytest.fixture
def api(playwright: Playwright, base_url: str, api_contract: Contract | None, request: pytest.FixtureRequest) -> Any:
    client = ApiClient.create(playwright, base_url=base_url, validate=_validator(api_contract, request))
    yield client
    client.dispose()


@pytest.fixture
def api_as(playwright: Playwright, base_url: str, api_contract: Contract | None, request: pytest.FixtureRequest) -> Any:
    clients: list[ApiClient] = []

    def open_as(role: Role) -> ApiClient:
        client = ApiClient.create(playwright, base_url=base_url, validate=_validator(api_contract, request))
        clients.append(client)
        credentials = require_credentials(app_config, role)
        client.login(credentials.username, credentials.password)
        return client

    yield open_as
    for client in clients:
        client.dispose()


@pytest.fixture
def authed_api(api_as: Callable[[Role], ApiClient]) -> ApiClient:
    return api_as("admin")


@pytest.fixture
def track_item(authed_api: ApiClient) -> Any:
    ids: list[int] = []

    def track(item: dict[str, Any]) -> None:
        ids.append(int(item["id"]))

    yield track
    for item_id in reversed(ids):
        response = authed_api.delete(f"/api/items/{item_id}")
        if response.status not in {204, 404}:
            raise RuntimeError(f"Cleanup of item {item_id} failed: HTTP {response.status}")


@pytest.fixture
def create_item(
    authed_api: ApiClient, track_item: Callable[[dict[str, Any]], None], random: Random
) -> Callable[..., dict[str, Any]]:
    def create(name: str | None = None) -> dict[str, Any]:
        chosen = item_name(random) if name is None else name
        response = authed_api.post("/api/items", {"name": chosen})
        if response.status != 201:
            raise RuntimeError(f"create_item failed: HTTP {response.status} {response.body}")
        if not isinstance(response.body, dict):
            raise RuntimeError("create_item did not return an item")
        track_item(response.body)
        return response.body

    return create


@pytest.fixture(scope="session")
def db() -> Any:
    if app_config.db is None:
        yield None
        return
    client = DbClient(app_config.db)
    yield client
    client.close()


def _role(request: pytest.FixtureRequest) -> str:
    marker = request.node.get_closest_marker("role")
    if marker is None or not marker.args:
        return "admin"
    return str(marker.args[0])


def _contract_enabled(request: pytest.FixtureRequest) -> bool:
    marker = request.node.get_closest_marker("contract")
    if marker is None:
        return bool(app_config.open_api_spec)
    if marker.args:
        return bool(marker.args[0])
    return True


def _validator(contract: Contract | None, request: pytest.FixtureRequest) -> Callable[[dict[str, Any]], None] | None:
    if contract is None or not _contract_enabled(request):
        return None

    def validate(response: dict[str, Any]) -> None:
        problems = contract.check(
            ContractResponse(
                method=str(response["method"]),
                path=str(response["path"]),
                status=int(response["status"]),
                body=response["body"],
            )
        )
        if problems:
            raise ContractViolation(problems)

    return validate


def _unit_only(args: list[str] | Any) -> bool:
    paths = [arg for arg in args if isinstance(arg, str) and not arg.startswith("-")]
    if not paths:
        return False
    return all(arg == "unit" or arg.startswith("unit/") or arg.startswith("unit\\") for arg in paths)


def _has_option(args: list[str], name: str) -> bool:
    return any(arg == name or arg.startswith(f"{name}=") for arg in args)


def _append(args: list[str], name: str, value: str) -> None:
    if not _has_option(args, name):
        args.extend([name, value])


def _write_report(pytest_config: pytest.Config) -> None:
    reporter = pytest_config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    stats = getattr(reporter, "stats", {})
    rerun_ids = {report.nodeid for report in stats.get("rerun", [])}
    tests: list[dict[str, Any]] = []
    counts = {"passed": 0, "failed": 0, "skipped": 0, "flaky": 0}

    def add(reports: list[Any], outcome: str) -> None:
        for report in reports:
            final = "flaky" if outcome == "passed" and report.nodeid in rerun_ids else outcome
            if final not in counts:
                continue
            counts[final] += 1
            location = getattr(report, "location", None)
            where = ""
            if isinstance(location, tuple) and len(location) >= 2:
                where = f"{location[0]}:{int(location[1]) + 1}"
            error = None
            if final == "failed":
                error = str(getattr(report, "longrepr", ""))
            tests.append({"nodeid": report.nodeid, "location": where, "outcome": final, "error": error})

    add(stats.get("passed", []), "passed")
    add(stats.get("failed", []), "failed")
    add(stats.get("error", []), "failed")
    add(stats.get("skipped", []), "skipped")
    destination = ROOT / "test-results" / "report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"stats": {**counts, "duration": round(time.monotonic() - _started, 3)}, "tests": tests}
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
