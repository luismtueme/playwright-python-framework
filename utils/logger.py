"""Minimal leveled logger. Set LOG_LEVEL to error, warn, info, or debug.

Framework internals log at debug so test output stays readable by default.
"""

from __future__ import annotations

from collections.abc import Callable

type Level = str
type LogFn = Callable[..., None]

LEVELS: dict[str, int] = {"error": 0, "warn": 1, "info": 2, "debug": 3}


def create_logger(scope: str, level: str | None = None) -> dict[str, LogFn]:
    """Build a logger. `level` defaults to the configured LOG_LEVEL."""
    if level is None:
        from config import config

        level = config.log_level
    threshold = LEVELS.get(level, LEVELS["warn"])

    def write(name: str, method: str) -> LogFn:
        def emit(message: str, *details: object) -> None:
            if LEVELS[name] <= threshold:
                suffix = "" if not details else " " + " ".join(str(item) for item in details)
                print(f"[{name.upper()}] [{scope}] {message}{suffix}", flush=True)

        _ = method
        return emit

    return {
        "error": write("error", "error"),
        "warn": write("warn", "warn"),
        "info": write("info", "log"),
        "debug": write("debug", "log"),
    }
