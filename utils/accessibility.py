"""Accessibility checks with axe-core.

Checks WCAG 2.1 A and AA rules plus axe best practices. Returns violations rather
than asserting, so the fixture can attach the report and fail with a readable summary.

axe-core (utils/vendor/axe.min.js) is MPL-2.0. See https://github.com/dequelabs/axe-core.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.sync_api import Page

TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]
_AXE_PATH = Path(__file__).resolve().parent / "vendor" / "axe.min.js"
_AXE_SOURCE = _AXE_PATH.read_text(encoding="utf-8")


def find_accessibility_violations(
    page: Page,
    *,
    exclude: list[str] | None = None,
    disable_rules: list[str] | None = None,
) -> list[dict[str, Any]]:
    page.evaluate(_AXE_SOURCE)
    options: dict[str, Any] = {"runOnly": {"type": "tag", "values": TAGS}}
    if disable_rules:
        options["rules"] = {rule: {"enabled": False} for rule in disable_rules}
    context: dict[str, Any] | None = {"exclude": [[selector] for selector in exclude]} if exclude else None
    violations = page.evaluate(
        """([context, options]) => axe.run(context || document, options).then((result) => result.violations)""",
        [context, options],
    )
    if not isinstance(violations, list):
        raise RuntimeError("axe-core did not return a violations list")
    return violations


def format_violations(violations: list[dict[str, Any]]) -> str:
    """One line per violation, with the elements involved, for assertion messages."""
    lines: list[str] = []
    for violation in violations:
        nodes = violation.get("nodes") or []
        targets = ", ".join(" ".join(node.get("target") or []) for node in nodes)
        impact = violation.get("impact")
        rule_id = violation.get("id")
        help_text = violation.get("help")
        help_url = violation.get("helpUrl")
        lines.append(f"[{impact}] {rule_id}: {help_text} ({targets}) {help_url}")
    return "\n".join(lines)
