"""Test policy linter.

Rules:
    unknown-marker       markers must be in ALLOWED_MARKERS, or be framework options
    marker-in-name       don't put @smoke (or any @marker) in the test name
    quarantine-ticket    quarantine requires @pytest.mark.issue("ABC-123")
    bare-skip            use pytest.mark.skipif(condition, reason=...), not a bare skip
    hard-wait            no page.wait_for_timeout() and no networkidle

Usage: uv run python -m utils.lint_tests
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from config import ROOT

ALLOWED_MARKERS = frozenset({"smoke", "api", "db", "a11y", "visual", "perf", "quarantine"})
FRAMEWORK_MARKERS = frozenset(
    {
        "role",
        "contract",
        "issue",
        "parametrize",
        "skipif",
        "usefixtures",
        "filterwarnings",
        "timeout",
        "xfail",
        "phone",
        "browser_context_args",
    }
)
SCAN_ROOTS = ("tests", "pages")


@dataclass(frozen=True)
class Problem:
    location: str
    title: str
    rule: str
    message: str


def lint_tree(tree: ast.AST, filename: str) -> list[Problem]:
    return _walk(tree, filename, module=tree, conditional_skip=False)


def _walk(node: ast.AST, filename: str, *, module: ast.AST, conditional_skip: bool) -> list[Problem]:
    problems: list[Problem] = []
    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
        problems.extend(_lint_test(node, filename, _class_markers(module, node)))
    problems.extend(_lint_waits(node, filename))
    problems.extend(_lint_skips(node, filename, conditional=conditional_skip))
    for child in ast.iter_child_nodes(node):
        nested = conditional_skip or (isinstance(node, ast.If) and _in_branch(node, child))
        problems.extend(_walk(child, filename, module=module, conditional_skip=nested))
    return problems


def _in_branch(statement: ast.If, child: ast.AST) -> bool:
    return child in statement.body or child in statement.orelse


def lint_source(source: str, filename: str) -> list[Problem]:
    return lint_tree(ast.parse(source), filename)


def lint_paths(root: Path = ROOT) -> list[Problem]:
    problems: list[Problem] = []
    for folder in SCAN_ROOTS:
        for path in sorted((root / folder).rglob("*.py")):
            problems.extend(lint_source(path.read_text(encoding="utf-8"), str(path.relative_to(root))))
    return problems


def _class_markers(tree: ast.AST, function: ast.FunctionDef) -> list[ast.expr]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(item is function for item in node.body):
            return list(node.decorator_list)
    return []


def _lint_test(function: ast.FunctionDef, filename: str, class_decorators: list[ast.expr]) -> list[Problem]:
    problems: list[Problem] = []
    location = f"{filename}:{function.lineno}"
    title = function.name
    markers = [_marker_name(decorator) for decorator in [*class_decorators, *function.decorator_list]]
    names = [name for name in markers if name]
    for name in names:
        if name in ALLOWED_MARKERS or name in FRAMEWORK_MARKERS:
            continue
        problems.append(
            Problem(
                location,
                title,
                "unknown-marker",
                f"Unknown marker {name}. Allowed: {', '.join(sorted(ALLOWED_MARKERS))} (see utils/lint_tests.py)",
            )
        )
    documented = ast.get_docstring(function) or ""
    if re.search(r"(^|\s)@[\w-]+", documented):
        problems.append(
            Problem(
                location,
                title,
                "marker-in-name",
                "Markers belong on @pytest.mark, not in the test name or docstring",
            )
        )
    if "quarantine" in names and "issue" not in names:
        problems.append(
            Problem(
                location,
                title,
                "quarantine-ticket",
                "Quarantined test needs a ticket: @pytest.mark.issue('ABC-123')",
            )
        )
    return problems


def _lint_waits(node: ast.AST, filename: str) -> list[Problem]:
    problems: list[Problem] = []
    location = f"{filename}:{getattr(node, 'lineno', 1)}"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "wait_for_timeout":
        problems.append(
            Problem(location, filename, "hard-wait", "Use a web-first assertion instead of wait_for_timeout()")
        )
    if isinstance(node, ast.Constant) and node.value == "networkidle":
        problems.append(
            Problem(
                location, filename, "hard-wait", "Don't wait for networkidle; use a locator assertion or expect.poll()"
            )
        )
    return problems


def _lint_skips(node: ast.AST, filename: str, *, conditional: bool) -> list[Problem]:
    if conditional or not isinstance(node, ast.Call):
        return []
    name = _call_name(node.func)
    if name == "pytest.skip":
        return [
            Problem(
                f"{filename}:{node.lineno}",
                filename,
                "bare-skip",
                "Use pytest.mark.skipif(condition, reason=...) so the skip stays conditional",
            )
        ]
    if name == "pytest.mark.skip":
        return [
            Problem(
                f"{filename}:{node.lineno}",
                filename,
                "bare-skip",
                "Use pytest.mark.skipif(condition, reason=...) so the skip stays conditional",
            )
        ]
    return []


def _marker_name(decorator: ast.expr) -> str | None:
    call = decorator
    if isinstance(decorator, ast.Call):
        call = decorator.func
    if not isinstance(call, ast.Attribute):
        return None
    if not isinstance(call.value, ast.Attribute):
        return None
    if call.value.attr != "mark" or _call_name(call.value.value) != "pytest":
        return None
    return call.attr


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def main() -> int:
    problems = lint_paths()
    for problem in problems:
        print(f"{problem.location}  {problem.title}\n  {problem.message}  [{problem.rule}]", file=sys.stderr)
    if problems:
        print(f"\nTest lint: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("Test lint: all tests follow the tag and quarantine policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
