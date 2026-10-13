import pytest

from config import DEMO_USERS, Credentials, app_url, build_config, load_defaults, require_credentials

DEFAULTS = load_defaults()


def test_uses_the_demo_app_and_demo_credentials_when_base_url_is_empty() -> None:
    built = build_config({}, DEFAULTS)
    assert built.use_demo_app is True
    assert built.users["admin"].username == DEMO_USERS["admin"].username
    assert built.users["viewer"].password == DEMO_USERS["viewer"].password


def test_never_falls_back_to_demo_credentials_for_a_real_app() -> None:
    built = build_config({"BASE_URL": "https://app.example.com"}, DEFAULTS)
    assert built.use_demo_app is False
    assert built.users["admin"].username is None
    with pytest.raises(RuntimeError, match="APP_USERNAME and APP_PASSWORD must be set for the admin role"):
        require_credentials(built)
    with pytest.raises(RuntimeError, match="VIEWER_USERNAME and VIEWER_PASSWORD must be set for the viewer role"):
        require_credentials(built, "viewer")


def test_environment_variables_override_defaults() -> None:
    built = build_config(
        {
            "BASE_URL": "https://app.example.com/",
            "TEST_BROWSER": "firefox",
            "HEADLESS": "false",
            "ACTION_TIMEOUT": "2500",
            "APP_USERNAME": "qa",
            "APP_PASSWORD": "secret",
        },
        DEFAULTS,
    )
    assert built.base_url == "https://app.example.com"
    assert built.api_base_url == "https://app.example.com"
    assert built.browser == "firefox"
    assert built.headless is False
    assert built.timeouts.action == 2500
    assert require_credentials(built) == Credentials(username="qa", password="secret")


def test_ci_defaults_headless_retries_and_fewer_workers() -> None:
    local = build_config({}, DEFAULTS)
    ci = build_config({"CI": "true"}, DEFAULTS)
    assert (local.headless, local.retries, local.workers) == (False, 0, 1)
    assert (ci.headless, ci.retries, ci.workers) == (True, 1, 2)


def test_database_config_is_present_only_when_db_host_is_set() -> None:
    assert build_config({}, DEFAULTS).db is None
    database = build_config({"DB_HOST": "localhost", "DB_USER": "u", "DB_PASSWORD": "p", "DB_NAME": "d"}, DEFAULTS).db
    assert database is not None
    assert database.host == "localhost"
    assert database.port == 3306
    assert database.user == "u"


def test_invalid_values_fail_fast_with_the_variable_name() -> None:
    with pytest.raises(ValueError, match="TEST_BROWSER must be one of"):
        build_config({"TEST_BROWSER": "ie11"}, DEFAULTS)
    with pytest.raises(ValueError, match="HEADLESS must be true or false"):
        build_config({"HEADLESS": "maybe"}, DEFAULTS)
    with pytest.raises(ValueError, match="WORKERS must be a non-negative integer"):
        build_config({"WORKERS": "-1"}, DEFAULTS)
    with pytest.raises(ValueError, match="VIDEO must be one of"):
        build_config({"VIDEO": "always"}, DEFAULTS)


def test_config_is_immutable() -> None:
    built = build_config({}, DEFAULTS)
    with pytest.raises(AttributeError):
        built.base_url = "changed"  # type: ignore[misc]


def test_app_url_uses_the_demo_port_when_base_url_is_empty() -> None:
    built = build_config({"DEMO_APP_PORT": "4242"}, DEFAULTS)
    assert app_url(built) == "http://127.0.0.1:4242"
    real = build_config({"BASE_URL": "https://app.example.com"}, DEFAULTS)
    assert app_url(real) == "https://app.example.com"
