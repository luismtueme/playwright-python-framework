"""Branches the happy-path unit tests do not reach."""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest
from PIL import Image

import contracts.models as models
from config import load_env_file, parse_integer
from demo_app.server import MemoryStore, MySqlStore, Request, _to_item, create_app, start_demo_app
from utils import accessibility, generate_api_types, lint_tests, pr_summary
from utils.api_client import ApiClient
from utils.auth_state import auth_file
from utils.check_leftover_data import main as leftover_main
from utils.contract import Contract, ContractResponse
from utils.db_client import DbClient
from utils.performance import measure_page
from utils.scaffold import scaffold
from utils.screenshots import _device_folder, expect_screenshot, pixel_difference


def test_generated_models_import() -> None:
    assert models.Item.__required_keys__ == frozenset({"id", "name", "createdAt"})


def test_env_file_does_not_override_and_strips_quotes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text('# comment\n\nHEADLESS="true"\nBROKEN\nKEEP=already\n', encoding="utf-8")
    monkeypatch.setenv("KEEP", "set")
    monkeypatch.delenv("HEADLESS", raising=False)
    load_env_file(env)
    assert __import__("os").environ["HEADLESS"] == "true"
    assert __import__("os").environ["KEEP"] == "set"
    with pytest.raises(ValueError, match="WORKERS"):
        parse_integer("WORKERS", "1.5", 1)
    with pytest.raises(ValueError, match="PORT"):
        parse_integer("PORT", "nope", 1)


def test_contract_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = Path("contracts/openapi.yaml")
    contract = Contract(str(spec))
    quiet = ContractResponse(method="GET", path="/api/items", status=200, body=None, body_unavailable=True)
    assert contract.check(quiet) == []
    ok = ContractResponse(
        method="GET",
        path="/api/items",
        status=200,
        body={"items": []},
    )
    assert contract.check(ok) == []
    assert contract.check(ok) == []
    contract.spec["components"]["responses"].pop("Unauthorized")
    with pytest.raises(RuntimeError, match="missing response"):
        contract.check(ContractResponse(method="GET", path="/api/items", status=401, body={}))

    listing = tmp_path / "list.yaml"
    listing.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="mapping"):
        Contract(str(listing))

    class _Response:
        def read(self) -> bytes:
            return spec.read_bytes()

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("utils.contract.urlopen", lambda *args, **kwargs: _Response())
    remote = Contract("https://example.test/openapi.yaml")
    assert remote.template_for("/api/items") == "/api/items"


def test_api_client_wrappers_and_plain_text() -> None:
    class _Response:
        status = 200
        headers: ClassVar[dict[str, str]] = {"content-type": "text/plain"}

        def text(self) -> str:
            return "ok"

    class _Context:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []
            self.disposed = False

        def fetch(self, url: str, **options: Any) -> _Response:
            self.calls.append((options["method"], url))
            if options["method"] == "POST" and url.endswith("/api/login"):
                return _Json('{"user": {}}')
            return _Response()

        def dispose(self) -> None:
            self.disposed = True

    class _Json(_Response):
        def __init__(self, payload: str) -> None:
            self._payload = payload

        def text(self) -> str:
            return self._payload

    seen: list[dict[str, Any]] = []
    context = _Context()
    client = ApiClient(
        context,  # type: ignore[arg-type]
        base_url="http://demo.test",
        validate=lambda exchange: seen.append(exchange),
        on_exchange=lambda exchange: seen.append(exchange),
        owns_context=True,
    )
    client.token = "secret-token"
    assert client.get("/api/items", params={"q": "1"}).body == "ok"
    assert client.put("/api/items/1", {"name": "x"}).status == 200
    assert client.delete("relative").status == 200
    with pytest.raises(RuntimeError, match="did not include a token"):
        client.login("demo", "demo-password")
    client.dispose()
    assert context.disposed is True
    assert seen
    exchanged = [item["request"]["headers"].get("Authorization") for item in seen if "request" in item]
    assert "***" in exchanged


def test_auth_file_and_leftover_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    assert auth_file("admin").endswith(".auth/admin.json")
    monkeypatch.setattr("utils.check_leftover_data.config", type("Cfg", (), {"db": None})())
    assert leftover_main() == 0
    assert "skipping" in capsys.readouterr().out

    class _Db:
        def query(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
            del sql, params
            return [{"id": 1}]

        def close(self) -> None:
            return None

    monkeypatch.setattr("utils.check_leftover_data.config", type("Cfg", (), {"db": object()})())
    monkeypatch.setattr("utils.check_leftover_data.DbClient", lambda db_config: _Db())
    assert leftover_main() == 1


def test_summary_and_lint_mains(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"stats": {"passed": 1}, "tests": []}), encoding="utf-8")
    monkeypatch.setattr("utils.pr_summary.sys.argv", ["pr_summary", str(report)])
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "9")
    assert pr_summary.main() == 0
    assert "actions/runs/9" in capsys.readouterr().out
    monkeypatch.setattr("utils.pr_summary.sys.argv", ["pr_summary"])
    assert pr_summary.main() == 1

    source = """
import pytest

@pytest.mark.smoke
class Suite:
    @pytest.mark.skip("later")
    def test_paused(self):
        pass
"""
    problems = lint_tests.lint_source(source, "tests/ui/test_suite.py")
    assert any(problem.rule == "bare-skip" for problem in problems)
    monkeypatch.setattr(lint_tests, "lint_paths", lambda root=None: [])
    assert lint_tests.main() == 0
    monkeypatch.setattr(
        lint_tests,
        "lint_paths",
        lambda root=None: [lint_tests.Problem("a:1", "t", "hard-wait", "no")],
    )
    assert lint_tests.main() == 1


def test_scaffold_spec_and_rejections(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "items_page.py").write_text("class ItemsPage: pass\n", encoding="utf-8")
    created = scaffold(tmp_path, "spec", ["orders", "--api", "--path", "/api/orders"])
    assert created == ["tests/api/test_orders.py"]
    ui = scaffold(tmp_path, "spec", ["filters", "--page", "items"])
    assert ui == ["tests/ui/test_filters.py"]
    with pytest.raises(ValueError, match="already exists"):
        scaffold(tmp_path, "spec", ["orders", "--api"])
    with pytest.raises(ValueError, match="page object"):
        scaffold(tmp_path, "spec", ["alone"])
    with pytest.raises(ValueError, match="Usage"):
        scaffold(tmp_path, "spec", [])
    with pytest.raises(ValueError, match=r"page\|spec"):
        scaffold(tmp_path, "nope", ["X"])
    with pytest.raises(ValueError, match="not a valid name"):
        scaffold(tmp_path, "page", ["123"])
    with pytest.raises(ValueError, match="Git Bash"):
        from utils.scaffold import check_path

        check_path("C:/windows")


def test_generate_check_write_and_unsupported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "models.py"
    monkeypatch.setattr(generate_api_types, "ROOT", tmp_path)
    monkeypatch.setattr(generate_api_types, "TARGET", target)
    assert generate_api_types.main([]) == 0
    assert generate_api_types.main(["--check"]) == 0
    target.write_text("stale\n", encoding="utf-8")
    assert generate_api_types.main(["--check"]) == 1
    rendered = generate_api_types.render_models(
        {
            "components": {
                "schemas": {
                    "Empty": {"type": "object"},
                    "Bag": {
                        "type": "object",
                        "properties": {
                            "ok": {"type": "boolean"},
                            "n": {"type": "number"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                }
            }
        }
    )
    assert "class Empty" in rendered
    assert "ok: NotRequired[bool]" in rendered
    with pytest.raises(RuntimeError, match="Unsupported"):
        generate_api_types.render_models({"components": {"schemas": {"Nope": {"type": "null"}}}})
    monkeypatch.setattr(generate_api_types, "config", type("Cfg", (), {"open_api_spec": ""})())
    with pytest.raises(RuntimeError, match="No OpenAPI"):
        generate_api_types.load_document()


def test_screenshots_missing_mismatch_and_device(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _Page:
        def screenshot(self, **kwargs: object) -> bytes:
            del kwargs
            return _png((1, 2, 3), (4, 4))

    monkeypatch.setattr("utils.screenshots.ROOT", tmp_path)
    monkeypatch.setattr("utils.screenshots.snapshot_path", lambda name: tmp_path / name)
    monkeypatch.delenv("UPDATE_SNAPSHOTS", raising=False)
    with pytest.raises(AssertionError, match="Missing baseline"):
        expect_screenshot(_Page(), "home.png")  # type: ignore[arg-type]
    baseline = tmp_path / "home.png"
    baseline.write_bytes(_png((9, 9, 9), (4, 4)))
    with pytest.raises(AssertionError, match="differs"):
        expect_screenshot(_Page(), "home.png")  # type: ignore[arg-type]
    assert pixel_difference(_png((0, 0, 0), (1, 1)), _png((0, 0, 0), (2, 2))) == 1
    assert _device_folder("Pixel 7") == "pixel-7"
    assert _device_folder(None) == "desktop"


def test_measure_and_axe_failures() -> None:
    class _Page:
        def wait_for_load_state(self, state: str) -> None:
            del state

        def evaluate(self, source: str, arg: object = None) -> object:
            del source, arg
            return "nope"

    with pytest.raises(RuntimeError, match="did not return an object"):
        measure_page(_Page())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="violations"):
        accessibility.find_accessibility_violations(_Page(), exclude=["#x"], disable_rules=["color-contrast"])  # type: ignore[arg-type]


def test_item_timestamps_and_server_errors() -> None:
    naive = _to_item({"id": 3, "name": "Pipe", "created_at": datetime(2026, 1, 5, 9, 0, 0)})
    assert naive["createdAt"].endswith("Z")
    plain = _to_item({"id": 3, "name": "Pipe", "created_at": "yesterday"})
    assert plain["createdAt"] == "yesterday"

    class _Missing:
        def execute(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> Any:
            del sql, params
            from utils.db_client import WriteResult

            return WriteResult(insert_id=4, affected_rows=1)

        def query(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
            del sql, params
            return []

        def one(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> None:
            del sql, params
            return None

        def close(self) -> None:
            return None

    with pytest.raises(RuntimeError, match="was not saved"):
        MySqlStore(db=_Missing()).create("x")  # type: ignore[arg-type]

    class _Boom(MemoryStore):
        def list(self) -> list[dict[str, Any]]:
            raise RuntimeError("db down")

    app = create_app(_Boom())
    login = app(Request("POST", "/api/login", {}, b'{"username":"demo","password":"demo-password"}'))
    headers = {"authorization": f"Bearer {login.body['token']}"}
    failed = app(Request("GET", "/api/items", headers, b""))
    assert failed.status == 500
    empty = app(Request("POST", "/api/items", headers, b""))
    assert empty.status == 400
    array = app(Request("POST", "/api/items", headers, b"[]"))
    assert array.status == 400
    gone = app(Request("DELETE", "/api/items/99", headers, b""))
    assert gone.status == 404


def test_http_delete_and_db_count() -> None:
    import urllib.error
    import urllib.request

    demo = start_demo_app(port=0)
    try:
        request = urllib.request.Request(demo.url + "/api/items/1", method="DELETE")
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=2)
        assert caught.value.code == 401
    finally:
        demo.close()

    class _Connection:
        def close(self) -> None:
            self.closed = True

    client = DbClient.__new__(DbClient)
    connection = _Connection()
    client._connections = []
    client._connections.append(connection)  # type: ignore[arg-type]
    client.close()
    assert connection.closed is True
    with pytest.raises(ValueError, match="Invalid table"):
        client.count("items;drop")


def _png(color: tuple[int, int, int], size: tuple[int, int]) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
