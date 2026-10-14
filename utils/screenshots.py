"""Screenshot comparison for visual tests.

Playwright Python exposes traces, videos, and failure screenshots, and this helper
compares full-page images with committed baselines. A difference of a few pixels is
allowed so anti-aliasing inside the Docker image does not flap. Update baselines
with `uv run python -m utils.visual --update`.
"""

from __future__ import annotations

import base64
import hashlib
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
        _write_baseline(path, actual)
        return
    expected = _read_baseline(path)
    if expected is None:
        digest = _hash_path(path)
        if digest.is_file():
            actual_hash = hashlib.sha256(actual).hexdigest()
            expected_hash = digest.read_text(encoding="utf-8").strip()
            if actual_hash != expected_hash:
                path.parent.mkdir(parents=True, exist_ok=True)
                actual_path = path.with_name(path.stem + "-actual.png")
                actual_path.write_bytes(actual)
                raise AssertionError(f"{name} hash {actual_hash} does not match {expected_hash}. See {actual_path}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        missing = path.with_name(path.stem + "-actual.png")
        missing.write_bytes(actual)
        raise AssertionError(f"Missing baseline {path.relative_to(ROOT)}. Run: uv run python -m utils.visual --update")
    difference = pixel_difference(actual, expected)
    if difference > MAX_DIFF_PIXELS:
        actual_path = path.with_name(path.stem + "-actual.png")
        actual_path.parent.mkdir(parents=True, exist_ok=True)
        actual_path.write_bytes(actual)
        raise AssertionError(f"{name} differs by {difference} pixels (budget {MAX_DIFF_PIXELS}). See {actual_path}")


def _baseline_text(path: Path) -> Path:
    return path.with_name(path.name + ".b64")


def _hash_path(path: Path) -> Path:
    return path.with_name(path.name + ".sha256")


def _write_baseline(path: Path, actual: bytes) -> None:
    # The PNG is a local preview. Commit the sha256; the base64 sibling is optional.
    _baseline_text(path).write_text(base64.b64encode(actual).decode("ascii") + "\n", encoding="utf-8")
    _hash_path(path).write_text(hashlib.sha256(actual).hexdigest() + "\n", encoding="utf-8")


def _read_baseline(path: Path) -> bytes | None:
    encoded = _baseline_text(path)
    if encoded.is_file():
        return base64.b64decode("".join(encoded.read_text(encoding="utf-8").split()))
    if path.is_file():
        return path.read_bytes()
    return None


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
