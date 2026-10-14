"""Run only quarantined tests. Their failures are reported and do not by themselves change policy.

Usage: uv run python -m utils.run_quarantine
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    environment = os.environ.copy()
    environment["PW_SUITE"] = "quarantine"
    environment["QUARANTINE"] = "true"
    completed = subprocess.run([sys.executable, "-m", "pytest", "tests", *sys.argv[1:]], env=environment, check=False)
    # Pytest exits 5 when the suite has no quarantined tests. That is a pass.
    if completed.returncode == 5:
        print("No quarantined tests.")
        return 0
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
