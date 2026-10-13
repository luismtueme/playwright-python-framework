"""Turn a pytest JSON report into a short Markdown summary for the PR comment.

Usage: uv run python -m utils.pr_summary test-results/report.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

COMMENT_MARKER = "<!-- playwright-summary -->"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def render_summary(report: dict[str, Any], *, run_url: str | None = None) -> str:
    stats = report.get("stats") or {}
    passed = int(stats.get("passed", 0))
    failed = int(stats.get("failed", 0))
    flaky = int(stats.get("flaky", 0))
    skipped = int(stats.get("skipped", 0))
    duration = float(stats.get("duration", 0))
    icon = "❌" if failed else "⚠️" if flaky else "✅"
    lines = [
        COMMENT_MARKER,
        f"### {icon} Playwright: {passed} passed, {failed} failed, {flaky} flaky, {skipped} skipped ({duration:.1f}s)",
        "",
    ]
    failures = [test for test in report.get("tests", []) if test.get("outcome") == "failed"]
    flakes = [test for test in report.get("tests", []) if test.get("outcome") == "flaky"]
    if failures:
        lines.extend(["**Failed**", "", "| Test | Error |", "|---|---|"])
        for test in failures:
            title = str(test.get("nodeid", "")).replace("|", "\\|")
            location = str(test.get("location", ""))
            error = _ANSI.sub("", str(test.get("error") or "")).splitlines()
            first = next((line.strip() for line in error if line.strip()), "")
            lines.append(f"| {title}<br>`{location}` | {first.replace('|', '\\|')[:160]} |")
        lines.append("")
    if flakes:
        lines.append("**Flaky** (failed, then passed on retry: fix or quarantine them)")
        lines.append("")
        for test in flakes:
            lines.append(f"- {test.get('nodeid')} (`{test.get('location')}`)")
        lines.append("")
    if run_url:
        lines.append(f"Traces, videos and the JUnit report: [run artifacts]({run_url})")
    return "\n".join(lines).rstrip() + "\n"


def merge_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine shard reports into one summary."""
    stats = {"passed": 0, "failed": 0, "flaky": 0, "skipped": 0, "duration": 0.0}
    tests: list[Any] = []
    for report in reports:
        for key in stats:
            stats[key] += (report.get("stats") or {}).get(key, 0)
        tests.extend(report.get("tests") or [])
    return {"stats": stats, "tests": tests}


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: uv run python -m utils.pr_summary <report.json> [more.json ...]", file=sys.stderr)
        return 1
    reports = [json.loads(Path(path).read_text(encoding="utf-8")) for path in sys.argv[1:]]
    report = reports[0] if len(reports) == 1 else merge_reports(reports)
    server = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_url = f"{server}/{repository}/actions/runs/{run_id}" if server and repository and run_id else None
    sys.stdout.write(render_summary(report, run_url=run_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
