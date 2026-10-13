"""List pytest files affected by a git range, for CI burn-in.

Prints ALL when shared framework code changed, nothing when no tests changed,
or one test path per line.

    uv run python -m utils.affected origin/main
"""

from __future__ import annotations

import subprocess
import sys

SHARED_PREFIXES = ("pages/", "utils/", "config/", "demo_app/", "contracts/", "tests/conftest.py")


def affected(base: str) -> list[str] | None:
    """Return changed test files, None when the whole suite is affected, or an empty list."""
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git diff failed")
    files = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if any(path.startswith(SHARED_PREFIXES) or path == "tests/conftest.py" for path in files):
        return None
    return [path for path in files if path.startswith("tests/") and path.endswith(".py") and "conftest.py" not in path]


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    try:
        files = affected(base)
    except RuntimeError as caught:
        print(caught, file=sys.stderr)
        return 1
    if files is None:
        print("ALL")
        return 0
    print("\n".join(files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
