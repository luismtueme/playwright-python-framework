"""Scaffold page objects and tests that follow this framework's conventions.

uv run python -m utils.scaffold page Settings --path /settings
uv run python -m utils.scaffold spec checkout --page items
uv run python -m utils.scaffold spec orders --api --path /api/orders
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from config import ROOT


@dataclass(frozen=True)
class Names:
    class_name: str
    fixture: str
    snake: str
    words: str


def split_words(value: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    words = [word.lower() for word in re.split(r"[\s_-]+", spaced) if word]
    if not words or not all(re.fullmatch(r"[a-z][a-z0-9]*", word) for word in words):
        raise ValueError(f'"{value}" is not a valid name: use letters and digits, starting with a letter')
    return words


def page_names(value: str) -> Names:
    words = split_words(value)
    if len(words) > 1 and words[-1] == "page":
        words = words[:-1]
    class_name = "".join(word.capitalize() for word in words) + "Page"
    fixture = "_".join(words) + "_page"
    return Names(class_name=class_name, fixture=fixture, snake="_".join(words), words=" ".join(words) + " page")


def spec_name(value: str) -> str:
    return "_".join(split_words(value))


def check_path(url_path: str) -> str:
    if re.match(r"^[A-Za-z]:[\\/]", url_path):
        raise ValueError(
            f'--path became "{url_path}": Git Bash rewrites arguments that start with "/". '
            "Run it from PowerShell, or prefix the command with MSYS_NO_PATHCONV=1"
        )
    if not re.fullmatch(r"/[\w\-./]*", url_path):
        raise ValueError(f'--path must start with "/", got "{url_path}"')
    return url_path


def page_object_source(names: Names, url_path: str) -> str:
    path = check_path(url_path)
    title = names.words[:1].upper() + names.words[1:]
    return f'''"""{title} ("{path}")."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from pages.base_page import BasePage


class {names.class_name}(BasePage):
    path = "{path}"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # Prefer role, label, and text locators; they match what users see
        self.heading: Locator = page.get_by_role("heading", level=1)
'''


def ui_spec_source(names: Names, title_words: str | None = None) -> str:
    title = (title_words or names.words).capitalize()
    return f"""import pytest
from playwright.sync_api import expect

from pages.{_module(names.class_name)} import {names.class_name}


@pytest.mark.smoke
def test_opens({names.fixture}: {names.class_name}) -> None:
    \"\"\"{title} opens.\"\"\"
    {names.fixture}.open()
    expect({names.fixture}.heading).to_be_visible()
"""


def api_spec_source(name: str, url_path: str) -> str:
    title = " ".join(split_words(name)).capitalize()
    path = check_path(url_path)
    return f'''import pytest

from utils.api_client import ApiClient


# Responses are checked against contracts/openapi.yaml: document {path} there first.
@pytest.mark.api
def test_responds(authed_api: ApiClient) -> None:
    """{title} responds."""
    response = authed_api.get("{path}")
    assert response.status == 200
'''


def register_fixture(source: str, names: Names) -> str:
    if f"def {names.fixture}(" in source:
        raise ValueError(f"tests/conftest.py already has a {names.fixture} fixture")
    import_anchor = "# END_PAGE_IMPORTS"
    fixture_anchor = "# END_PAGE_FIXTURES"
    if import_anchor not in source or fixture_anchor not in source:
        raise ValueError("Could not find the page-object anchors in tests/conftest.py")
    module = _module(names.class_name)
    source = source.replace(
        import_anchor,
        f"from pages.{module} import {names.class_name}\n{import_anchor}",
    )
    fixture = (
        f"@pytest.fixture\n"
        f"def {names.fixture}(page: Page) -> {names.class_name}:\n"
        f"    return {names.class_name}(page)\n\n\n"
        f"{fixture_anchor}"
    )
    return source.replace(fixture_anchor, fixture)


def add_accessibility_check(source: str, names: Names) -> str:
    import_anchor = "# END_A11Y_IMPORTS"
    check_anchor = "# LOGGED_OUT_A11Y"
    if import_anchor not in source or check_anchor not in source:
        raise ValueError("Could not find where to add the accessibility check")
    module = _module(names.class_name)
    source = source.replace(import_anchor, f"from pages.{module} import {names.class_name}\n{import_anchor}")
    signature = (
        f"def test_{names.snake}_page({names.fixture}: {names.class_name}, "
        f"check_accessibility: CheckAccessibility) -> None:\n"
    )
    check = (
        signature
        + f"    {names.fixture}.open()\n"
        + f"    expect({names.fixture}.heading).to_be_visible()\n"
        + "    check_accessibility()\n\n\n"
    )
    return source.replace(check_anchor, check + check_anchor)


def parse_args(argv: list[str]) -> tuple[str | None, dict[str, str | bool]]:
    options: dict[str, str | bool] = {}
    name: str | None = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg.startswith("--"):
            key = arg[2:]
            nxt = argv[index + 1] if index + 1 < len(argv) else None
            if nxt is not None and not nxt.startswith("--"):
                options[key] = nxt
                index += 2
            else:
                options[key] = True
                index += 1
        else:
            if name is None:
                name = arg
            index += 1
    return name, options


def scaffold(root: Path, command: str | None, argv: list[str]) -> list[str]:
    name, options = parse_args(argv)
    created: list[str] = []

    def write(relative: str, content: str, *, overwrite: bool = False) -> None:
        path = root / relative
        if path.exists() and not overwrite:
            raise ValueError(f"{relative} already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(relative)

    def read(relative: str) -> str:
        return (root / relative).read_text(encoding="utf-8")

    if command == "page":
        if not name:
            raise ValueError("Usage: uv run python -m utils.scaffold page <Name> --path /<url>")
        names = page_names(name)
        url_path = check_path(_option(options, "path") or f"/{names.snake.replace('_', '-')}")
        page_file = f"pages/{_module(names.class_name)}.py"
        spec_file = f"tests/ui/test_{names.snake}.py"
        for relative in (page_file, spec_file):
            if (root / relative).exists():
                raise ValueError(f"{relative} already exists")
        fixtures = register_fixture(read("tests/conftest.py"), names)
        accessibility = add_accessibility_check(read("tests/ui/test_accessibility.py"), names)
        write(page_file, page_object_source(names, url_path))
        write(spec_file, ui_spec_source(names))
        write("tests/conftest.py", fixtures, overwrite=True)
        write("tests/ui/test_accessibility.py", accessibility, overwrite=True)
        return created

    if command == "spec":
        if not name:
            raise ValueError(
                "Usage: uv run python -m utils.scaffold spec <name> (--page <page> | --api [--path /api/x])"
            )
        file_name = spec_name(name)
        if options.get("api") is True or "api" in options:
            write(
                f"tests/api/test_{file_name}.py",
                api_spec_source(name, _option(options, "path") or f"/api/{file_name.replace('_', '-')}"),
            )
            return created
        page = _option(options, "page")
        if not page:
            raise ValueError("UI specs need a page object: --page <name>, for example --page items")
        names = page_names(page)
        if not (root / "pages" / f"{_module(names.class_name)}.py").exists():
            raise ValueError(f"pages/{_module(names.class_name)}.py not found; create it with the page command")
        write(f"tests/ui/test_{file_name}.py", ui_spec_source(names, " ".join(split_words(name))))
        return created

    raise ValueError("Usage: uv run python -m utils.scaffold <page|spec> <name> [options]")


def _option(options: dict[str, str | bool], key: str) -> str | None:
    value = options.get(key)
    if value is True:
        raise ValueError(f"--{key} needs a value")
    return value if isinstance(value, str) else None


def _module(class_name: str) -> str:
    words = split_words(class_name)
    return "_".join(words)


def main() -> int:
    try:
        created = scaffold(ROOT, sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2:])
    except (ValueError, OSError) as caught:
        print(caught, file=sys.stderr)
        return 1
    print("\n".join(f"  {file}" for file in created))
    print("Next: uv run ruff check . && uv run mypy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
