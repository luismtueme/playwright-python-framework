"""Small helpers shared by the specs: steps, polling, and a defined() check."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


@contextmanager
def step(name: str) -> Any:
    """Print a named step so the pytest log reads like a scenario."""
    print(f"STEP {name}", flush=True)
    yield


def defined[T](value: T | None, message: str) -> T:
    """Return `value`, or raise `message` if it is None."""
    if value is None:
        raise AssertionError(message)
    return value


class Poll:
    def __init__(self, producer: Callable[[], Any], *, timeout_ms: int, message: str) -> None:
        self._producer = producer
        self._timeout_ms = timeout_ms
        self._message = message

    def _until(self, predicate: Callable[[Any], bool]) -> Any:
        deadline = time.monotonic() + self._timeout_ms / 1000
        last: Any = None
        while True:
            last = self._producer()
            if predicate(last):
                return last
            if time.monotonic() >= deadline:
                detail = self._message or f"last value was {last!r}"
                raise AssertionError(detail)
            time.sleep(0.1)

    def to_equal(self, expected: Any) -> None:
        self._until(lambda value: value == expected)

    def to_be(self, expected: Any) -> None:
        self.to_equal(expected)

    def to_match(self, expected: dict[str, Any]) -> None:
        def matches(value: Any) -> bool:
            return isinstance(value, dict) and all(value.get(key) == item for key, item in expected.items())

        self._until(matches)


def expect_poll(producer: Callable[[], Any], *, timeout_ms: int = 5000, message: str = "") -> Poll:
    """Retry until a value that isn't on the page matches. The Playwright stand-in for expect.poll."""
    return Poll(producer, timeout_ms=timeout_ms, message=message)
