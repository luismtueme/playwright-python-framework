import ast
import io
from pathlib import Path

import pytest
from PIL import Image

from utils import accessibility, lint_tests, scaffold
from utils.check_leftover_data import find_leftovers
from utils.generate_api_types import TARGET, load_document, render_models
from utils.logger import create_logger
from utils.performance import measure_page, over_budget
from utils.pr_summary import COMMENT_MARKER, merge_reports, render_summary
from utils.screenshots import expect_screenshot, pixel_difference, snapshot_path
from utils.test_data import Random, item_name, parse_seed, seed_for


def test_seed_is_stable_and_rejects_garbage() -> None:
    assert parse_seed("123") == 123
    with pytest.raises(ValueError, match="TEST_SEED"):
        parse_seed("nope")
    assert seed_for("same", 7) == seed_for("same", 7)
    assert seed_for("same", 7) != seed_for("other", 7)
    random = Random(1)
    again = Random(1)
    assert [random.int(1, 5) for _ in range(4)] == [again.int(1, 5) for _ in range(4)]
    assert " " in item_name(Random(2))
    with pytest.raises(ValueError, match="non-empty"):
        Random(1).pick(())


def test_logger_respects_the_level(capsys: pytest.CaptureFixture[str]) -> None:
    log = create_logger("api", "warn")
    log["debug"]("hidden")
    log["error"]("visible")
    output = capsys.readouterr().out
    assert "hidden" not in output
    assert "visible" in output
    assert "[ERROR] [api]" in output


def test_lint_flags_unknown_markers_quarantine_skips_and_waits() -> None:
    source = '''
import pytest

@pytest.mark.wip
def test_login():
    """Logs in @smoke."""
    page.wait_for_timeout(1000)
    page.wait_for_load_state("networkidle")
    pytest.skip("later")

@pytest.mark.quarantine
def test_blocked():
    pass

@pytest.mark.smoke
def test_ok():
    pass
'''
    problems = lint_tests.lint_source(source, "tests/ui/test_sample.py")
    rules = {problem.rule for problem in problems}
    assert {"unknown-marker", "marker-in-name", "quarantine-ticket", "bare-skip", "hard-wait"} <= rules
    assert lint_tests.lint_paths() == []


def test_scaffold_names_and_registration(tmp_path: Path) -> None:
    names = scaffold.page_names("UserProfile")
    assert names.class_name == "UserProfilePage"
    assert names.fixture == "user_profile_page"
    source = scaffold.page_object_source(names, "/profile")
    assert 'path = "/profile"' in source
    assert scaffold.spec_name("Check Out") == "check_out"
    name, options = scaffold.parse_args(["Settings", "--path", "/settings", "--api"])
    assert name == "Settings"
    assert options["path"] == "/settings"
    assert options["api"] is True
    with pytest.raises(ValueError, match="start with"):
        scaffold.check_path("settings")

    conftest = tmp_path / "tests" / "conftest.py"
    a11y = tmp_path / "tests" / "ui" / "test_accessibility.py"
    (tmp_path / "pages").mkdir(parents=True)
    conftest.parent.mkdir(parents=True)
    a11y.parent.mkdir(parents=True)
    conftest.write_text(
        "from pages.login_page import LoginPage\n# END_PAGE_IMPORTS\n\n"
        "@pytest.fixture\n"
        "def login_page(page: Page) -> LoginPage:\n"
        "    return LoginPage(page)\n\n\n"
        "# END_PAGE_FIXTURES\n",
        encoding="utf-8",
    )
    a11y.write_text(
        "from pages.login_page import LoginPage\n# END_A11Y_IMPORTS\n\n# LOGGED_OUT_A11Y\n",
        encoding="utf-8",
    )
    created = scaffold.scaffold(tmp_path, "page", ["Settings", "--path", "/settings"])
    assert "pages/settings_page.py" in created
    assert "def settings_page(" in conftest.read_text(encoding="utf-8")
    assert "def test_settings_page(" in a11y.read_text(encoding="utf-8")
    ast.parse((tmp_path / "pages" / "settings_page.py").read_text(encoding="utf-8"))


def test_summary_lists_failures_and_flakes() -> None:
    report = {
        "stats": {"passed": 1, "failed": 1, "flaky": 1, "skipped": 0, "duration": 1.25},
        "tests": [
            {
                "nodeid": "tests/ui/test_login.py::test_logs_in",
                "location": "tests/ui/test_login.py:12",
                "outcome": "failed",
                "error": "\x1b[31mboom\x1b[0m",
            },
            {
                "nodeid": "tests/ui/test_form.py::test_one",
                "location": "tests/ui/test_form.py:4",
                "outcome": "flaky",
                "error": None,
            },
        ],
    }
    rendered = render_summary(report, run_url="https://example.test/run")
    assert rendered.startswith(COMMENT_MARKER)
    assert "1 passed, 1 failed, 1 flaky" in rendered
    assert "boom" in rendered
    assert "Flaky" in rendered
    assert "https://example.test/run" in rendered
    merged = merge_reports([report, {"stats": {"passed": 2, "duration": 1}, "tests": []}])
    assert merged["stats"]["passed"] == 3
    assert merged["stats"]["failed"] == 1


def test_leftovers_and_budgets() -> None:
    class Fake:
        def query(self, sql: str, params: list[object] | tuple[object, ...] = ()) -> list[dict[str, object]]:
            del params
            if "items" in sql:
                return [{"id": 1}]
            return []

    found = find_leftovers(Fake(), ("items", "other"))
    assert found[0][0] == "items"
    assert over_budget({"ttfb": 800, "cls": 0.01}, {"ttfb": 500, "cls": 0.1, "$comment": "ignore"}) == [
        "ttfb 800.0 > budget 500"
    ]
    assert over_budget({"ttfb": 10}, {"ttfb": 500}) == []


class _Page:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def wait_for_load_state(self, state: str) -> None:
        assert state == "load"

    def evaluate(self, source: str, arg: object = None) -> object:
        if arg is None and "navigation" not in source:
            return None
        return self.payload

    def screenshot(self, **kwargs: object) -> bytes:
        del kwargs
        return _png((0, 0, 0))


def _png(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (2, 2), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_measure_page_and_accessibility_and_screenshots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    metrics = measure_page(_Page({"ttfb": 12, "load": 40}))  # type: ignore[arg-type]
    assert metrics["ttfb"] == 12
    violations = accessibility.format_violations(
        [
            {
                "impact": "serious",
                "id": "label",
                "help": "Add a label",
                "helpUrl": "https://axe.test",
                "nodes": [{"target": ["#name"]}],
            }
        ]
    )
    assert "label" in violations
    assert accessibility.find_accessibility_violations(_Page([])) == []  # type: ignore[arg-type]

    monkeypatch.setattr("utils.screenshots.snapshot_path", lambda name: tmp_path / name)
    monkeypatch.setenv("UPDATE_SNAPSHOTS", "1")
    expect_screenshot(_Page(None), "form-page.png")  # type: ignore[arg-type]
    assert (tmp_path / "form-page.png").exists()
    assert pixel_difference(_png((0, 0, 0)), _png((0, 0, 0))) == 0
    assert pixel_difference(_png((0, 0, 0)), _png((255, 0, 0))) == 4
    assert snapshot_path("form-page.png").name == "form-page.png"


def test_generated_models_match_the_contract() -> None:
    rendered = render_models(load_document())
    assert "class Item(TypedDict):" in rendered
    assert TARGET.read_text(encoding="utf-8") == rendered
