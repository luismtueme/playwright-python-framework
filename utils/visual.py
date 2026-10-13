"""Run the visual tests inside the official Playwright Python image.

Screenshots then render the same on every machine. Inside that image the runner
walks desktop, Pixel 7, and iPhone 15 unless TEST_DEVICE selects one profile.

    uv run python -m utils.visual
    uv run python -m utils.visual --update
    TEST_DEVICE="Pixel 7" uv run python -m utils.visual

Requires Docker. Extra arguments are passed to pytest. --update writes baselines
(UPDATE_SNAPSHOTS=1); it is not a pytest flag.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from importlib.metadata import version

from config import ROOT

DEVICES = ("", "Pixel 7", "iPhone 15")


def main() -> int:
    if os.environ.get("IN_DOCKER") == "true":
        return _run_here(sys.argv[1:])
    return _run_in_docker(sys.argv[1:])


def _run_here(argv: list[str]) -> int:
    update = "--update" in argv
    extra = [arg for arg in argv if arg != "--update"]
    selected = os.environ.get("TEST_DEVICE")
    devices = [selected] if selected else list(DEVICES)
    code = 0
    for device in devices:
        label = device or "desktop"
        print(f"Visual: {label}")
        env = os.environ.copy()
        env["TEST_DEVICE"] = device
        env["PW_SUITE"] = "visual"
        env["IN_DOCKER"] = "true"
        env["HEADLESS"] = "true"
        if update:
            env["UPDATE_SNAPSHOTS"] = "1"
        completed = subprocess.run([sys.executable, "-m", "pytest", "tests/visual", *extra], env=env, check=False)
        code = code or completed.returncode
    return code


def _run_in_docker(argv: list[str]) -> int:
    if shutil.which("docker") is None:
        print("Could not start Docker. Visual tests need Docker installed.", file=sys.stderr)
        return 1
    playwright_version = version("playwright")
    image = f"mcr.microsoft.com/playwright/python:v{playwright_version}-noble"
    inner = "pip install --quiet uv && uv sync --frozen --no-dev && uv run python -m utils.visual " + shlex.join(argv)
    command = [
        "docker",
        "run",
        "--rm",
        "--ipc=host",
        "-v",
        f"{ROOT}:/work",
        "-w",
        "/work",
        "-e",
        "CI=true",
        "-e",
        "VISUAL=true",
        "-e",
        "IN_DOCKER=true",
        "-e",
        "HEADLESS=true",
        "-e",
        "PW_SUITE=visual",
        "-e",
        f"TEST_DEVICE={os.environ.get('TEST_DEVICE', '')}",
        "-e",
        "BASE_URL=",
        "-e",
        "DB_HOST=",
        image,
        "bash",
        "-lc",
        inner,
    ]
    print(f"Running visual tests in {image}")
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
