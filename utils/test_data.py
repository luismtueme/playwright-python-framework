"""Reproducible test data.

Every run has a seed (TEST_SEED, or a new one per run). Each test gets its own
generator derived from that seed and its node id, so data is realistic, different
between runs, and exactly the same when you re-run with the seed from a failed
test's report:

    TEST_SEED=1234567 uv run pytest tests/ui/test_items.py
"""

from __future__ import annotations

import os

ASSETS = ("Manhole", "Sewer main", "Lateral", "Catch basin", "Outfall", "Culvert", "Lift station")
WORK = ("inspection", "cleaning", "repair", "CCTV survey", "rehabilitation", "condition review")


def imul(left: int, right: int) -> int:
    """32-bit signed multiply, matching JavaScript Math.imul."""
    left &= 0xFFFFFFFF
    right &= 0xFFFFFFFF
    if left >= 0x80000000:
        left -= 0x100000000
    if right >= 0x80000000:
        right -= 0x100000000
    return (left * right) & 0xFFFFFFFF


def parse_seed(value: str | None) -> int:
    """Parse TEST_SEED, or draw a new seed when it is unset."""
    if value is None or value == "":
        return int.from_bytes(os.urandom(4), "big") % (2**31)
    if not value.isdigit():
        raise ValueError(f'TEST_SEED must be an integer, got "{value}"')
    return int(value)


class Random:
    """A small seeded generator (mulberry32). Same seed, same sequence."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._state = seed & 0xFFFFFFFF

    def next(self) -> float:
        """Float in [0, 1)."""
        self._state = (self._state + 0x6D2B79F5) & 0xFFFFFFFF
        value = self._state
        value = imul(value ^ (value >> 15), value | 1)
        value ^= (value + imul(value ^ (value >> 7), value | 61)) & 0xFFFFFFFF
        return ((value ^ (value >> 14)) & 0xFFFFFFFF) / 2**32

    def int(self, minimum: int, maximum: int) -> int:
        """Integer in [minimum, maximum]."""
        return minimum + int(self.next() * (maximum - minimum + 1))

    def pick[T](self, values: tuple[T, ...] | list[T]) -> T:
        if not values:
            raise ValueError("pick() needs a non-empty list")
        return values[self.int(0, len(values) - 1)]


def seed_for(title: str, run_seed: int | None = None) -> int:
    """Seed for one test: stable for a given run seed and test title."""
    current = RUN_SEED if run_seed is None else run_seed
    hashed = current & 0xFFFFFFFF
    for character in title:
        hashed = imul(hashed ^ ord(character), 0x01000193) & 0xFFFFFFFF
    return hashed


def item_name(random: Random) -> str:
    """A realistic item name, for example "Lateral 214 CCTV survey"."""
    return f"{random.pick(ASSETS)} {random.int(1, 999)} {random.pick(WORK)}"


RUN_SEED = parse_seed(os.environ.get("TEST_SEED"))
