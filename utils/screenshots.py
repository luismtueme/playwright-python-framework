"""Screenshot comparison for visual tests.

Playwright Python exposes traces, videos, and failure screenshots, and this helper
compares full-page images with committed baselines. A difference of a few pixels is
allowed so anti-aliasing inside the Docker image does not flap. Update baselines
with `uv run python -m utils.visual --update`.
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import Locator, Page

from config import ROOT, config

MAX_DIFF_PIXELS = 10


def snapshot_path(name: str) -> Path:
    folder = _device_folder(config.device)
    return ROOT / "tests" / "visual" / "__screenshots__" / folder / name


def expect_screenshot(page: Page, name: str, *, full_page: bool = False, mask: list[Locator] | None = None) -> None:
    actual = page.screenshot(full_page=full_page, mask=mask or [], animations="disabled", caret="hide")
    path = snapshot_path(name)
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(actual)
        return
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        missing = path.with_name(path.stem + "-actual.png")
        missing.write_bytes(actual)
        raise AssertionError(f"Missing baseline {path.relative_to(ROOT)}. Run: uv run python -m utils.visual --update")
    difference = pixel_difference(actual, path.read_bytes())
    if difference > MAX_DIFF_PIXELS:
        actual_path = path.with_name(path.stem + "-actual.png")
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        actual_path.write_bytes(actual)
        raise AssertionError(f"{name} differs by {difference} pixels (budget {MAX_DIFF_PIXELS}). See {actual_path}")


def pixel_difference(actual: bytes, expected: bytes) -> int:
    left = Image.open(io.BytesIO(actual)).convert("RGB")
    right = Image.open(io.BytesIO(expected)).convert("RGB")
    if left.size != right.size:
        return left.size[0] * left.size[1]
    diff = ImageChops.difference(left, right)
    channels = len(diff.getbands())
    raw = diff.tobytes()
    black = b"\x00" * channels
    return sum(1 for offset in range(0, len(raw), channels) if raw[offset : offset + channels] != black)


def _device_folder(device: str | None) -> str:
    if not device:
        return "desktop"
    return re.sub(r"[^a-z0-9]+", "-", device.lower()).strip("-")
