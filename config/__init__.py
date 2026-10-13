"""Single source of test configuration for pytest, the demo app, and the scripts.

Precedence: environment variables > .env file > config/test_config.json defaults.
Secrets (credentials, tokens, DB passwords) come only from the environment, never
from committed files. See .env.example for every supported variable.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent

type BrowserName = Literal["chromium", "firefox", "webkit"]
type ArtifactMode = Literal["off", "on", "retain-on-failure"]
type Role = Literal["admin", "viewer"]

BROWSERS: tuple[BrowserName, ...] = ("chromium", "firefox", "webkit")
ARTIFACT_MODES: tuple[ArtifactMode, ...] = ("off", "on", "retain-on-failure")
ROLES: tuple[Role, ...] = ("admin", "viewer")

ROLE_ENV: dict[Role, dict[str, str]] = {
    "admin": {"username": "APP_USERNAME", "password": "APP_PASSWORD"},
    "viewer": {"username": "VIEWER_USERNAME", "password": "VIEWER_PASSWORD"},
}

# Demo app credentials are public on purpose: they only unlock the bundled demo app
DEMO_USERS: dict[Role, Credentials] = {}


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str


DEMO_USERS["admin"] = Credentials(username="demo", password="demo-password")
DEMO_USERS["viewer"] = Credentials(username="viewer", password="viewer-password")


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    user: str | None = None
    password: str | None = None
    database: str | None = None


@dataclass(frozen=True)
class Viewport:
    width: int
    height: int


@dataclass(frozen=True)
class Timeouts:
    action: int
    navigation: int
    expect: int
    test: int


@dataclass(frozen=True)
class Defaults:
    base_url: str
    environment: str
    browser: BrowserName
    headless: bool
    viewport: Viewport
    timeouts: Timeouts
    video: ArtifactMode
    trace: ArtifactMode


@dataclass(frozen=True)
class RoleCredentials:
    username: str | None
    password: str | None


@dataclass(frozen=True)
class Config:
    is_ci: bool
    environment: str
    use_demo_app: bool
    base_url: str
    demo_app_port: int
    api_base_url: str
    browser: BrowserName
    device: str | None
    headless: bool
    viewport: Viewport
    timeouts: Timeouts
    retries: int
    workers: int
    video: ArtifactMode
    trace: ArtifactMode
    users: dict[Role, RoleCredentials]
    db: DbConfig | None
    log_level: str
    quarantine: bool
    visual: bool
    in_docker: bool
    open_api_spec: str
    all_tests: bool


def load_env_file(file: Path | None = None) -> None:
    """Load KEY=VALUE lines into the environment without overriding existing variables."""
    path = file if file is not None else ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def parse_boolean(name: str, value: str | None, fallback: bool) -> bool:
    if value is None or value == "":
        return fallback
    if value.lower() in {"1", "true", "yes"}:
        return True
    if value.lower() in {"0", "false", "no"}:
        return False
    raise ValueError(f'{name} must be true or false, got "{value}"')


def parse_integer(name: str, value: str | None, fallback: int) -> int:
    if value is None or value == "":
        return fallback
    try:
        number = int(value)
    except ValueError:
        number = -1
    if number < 0 or str(number) != value.strip():
        raise ValueError(f'{name} must be a non-negative integer, got "{value}"')
    return number


def one_of[T: str](name: str, value: str, allowed: tuple[T, ...] | list[T]) -> T:
    if value not in allowed:
        joined = ", ".join(allowed)
        raise ValueError(f'{name} must be one of {joined}, got "{value}"')
    return value  # type: ignore[return-value]


def _trim_slash(url: str) -> str:
    return url.rstrip("/")


def build_config(env: dict[str, str | None], defaults: Defaults) -> Config:
    """Build configuration from defaults and an environment. Unit-tested without touching os.environ."""
    is_ci = parse_boolean("CI", env.get("CI"), False)
    base_url = _trim_slash(env.get("BASE_URL") or defaults.base_url or "")
    use_demo_app = base_url == ""

    users: dict[Role, RoleCredentials] = {}
    for role in ROLES:
        username = env.get(ROLE_ENV[role]["username"]) or (DEMO_USERS[role].username if use_demo_app else None)
        password = env.get(ROLE_ENV[role]["password"]) or (DEMO_USERS[role].password if use_demo_app else None)
        users[role] = RoleCredentials(username=username or None, password=password or None)

    db = None
    if env.get("DB_HOST"):
        db = DbConfig(
            host=env["DB_HOST"] or "",
            port=parse_integer("DB_PORT", env.get("DB_PORT"), 3306),
            user=env.get("DB_USER"),
            password=env.get("DB_PASSWORD"),
            database=env.get("DB_NAME"),
        )

    device = (env.get("TEST_DEVICE") or "").strip() or None
    spec = env.get("OPENAPI_SPEC") or (str(ROOT / "contracts" / "openapi.yaml") if use_demo_app else "")

    return Config(
        is_ci=is_ci,
        environment=env.get("TEST_ENV") or defaults.environment,
        use_demo_app=use_demo_app,
        base_url=base_url,
        demo_app_port=parse_integer("DEMO_APP_PORT", env.get("DEMO_APP_PORT"), 4173),
        api_base_url=_trim_slash(env.get("API_BASE_URL") or base_url),
        browser=one_of("TEST_BROWSER", env.get("TEST_BROWSER") or defaults.browser, BROWSERS),
        device=device,
        headless=parse_boolean("HEADLESS", env.get("HEADLESS"), True if is_ci else defaults.headless),
        viewport=defaults.viewport,
        timeouts=Timeouts(
            action=parse_integer("ACTION_TIMEOUT", env.get("ACTION_TIMEOUT"), defaults.timeouts.action),
            navigation=parse_integer("NAVIGATION_TIMEOUT", env.get("NAVIGATION_TIMEOUT"), defaults.timeouts.navigation),
            expect=parse_integer("EXPECT_TIMEOUT", env.get("EXPECT_TIMEOUT"), defaults.timeouts.expect),
            test=parse_integer("TEST_TIMEOUT", env.get("TEST_TIMEOUT"), defaults.timeouts.test),
        ),
        retries=parse_integer("RETRIES", env.get("RETRIES"), 1 if is_ci else 0),
        workers=parse_integer("WORKERS", env.get("WORKERS"), 2 if is_ci else 1),
        video=one_of("VIDEO", env.get("VIDEO") or defaults.video, ARTIFACT_MODES),
        trace=one_of("TRACE", env.get("TRACE") or defaults.trace, ARTIFACT_MODES),
        users=users,
        db=db,
        log_level=env.get("LOG_LEVEL") or ("info" if is_ci else "warn"),
        quarantine=parse_boolean("QUARANTINE", env.get("QUARANTINE"), False),
        visual=parse_boolean("VISUAL", env.get("VISUAL"), False),
        in_docker=parse_boolean("IN_DOCKER", env.get("IN_DOCKER"), False),
        open_api_spec=spec,
        all_tests=parse_boolean("ALL_TESTS", env.get("ALL_TESTS"), False),
    )


def app_url(current: Config) -> str:
    """URL of the app under test: BASE_URL, or the bundled demo app."""
    return current.base_url or f"http://127.0.0.1:{current.demo_app_port}"


def require_credentials(current: Config, role: Role = "admin") -> Credentials:
    """Return a role's credentials, or raise naming the variables to set."""
    found = current.users[role]
    if not found.username or not found.password:
        variables = ROLE_ENV[role]
        raise RuntimeError(
            f"{variables['username']} and {variables['password']} must be set for the {role} role. "
            "Copy .env.example to .env."
        )
    return Credentials(username=found.username, password=found.password)


def load_defaults(path: Path | None = None) -> Defaults:
    file = path if path is not None else Path(__file__).resolve().parent / "test_config.json"
    raw = json.loads(file.read_text(encoding="utf-8"))
    timeouts = raw["timeouts"]
    viewport = raw["viewport"]
    return Defaults(
        base_url=raw["baseUrl"],
        environment=raw["environment"],
        browser=one_of("browser", raw["browser"], BROWSERS),
        headless=bool(raw["headless"]),
        viewport=Viewport(width=int(viewport["width"]), height=int(viewport["height"])),
        timeouts=Timeouts(
            action=int(timeouts["action"]),
            navigation=int(timeouts["navigation"]),
            expect=int(timeouts["expect"]),
            test=int(timeouts["test"]),
        ),
        video=one_of("video", raw["video"], ARTIFACT_MODES),
        trace=one_of("trace", raw["trace"], ARTIFACT_MODES),
    )


def _env_map() -> dict[str, str | None]:
    return dict(os.environ)


load_env_file()
config = build_config(_env_map(), load_defaults())
