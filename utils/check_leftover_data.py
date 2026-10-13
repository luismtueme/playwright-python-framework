"""Fail if tests left data behind in the database.

Run after the suite in CI. Every test is expected to delete what it creates
(see create_item / track_item). No-op when DB_HOST is not set.

Usage: uv run python -m utils.check_leftover_data
"""

from __future__ import annotations

import json
import sys
from typing import Any, Protocol

from config import config
from utils.db_client import DbClient

TABLES = ("items",)


class Queryable(Protocol):
    def query(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]: ...


def find_leftovers(db: Queryable, tables: tuple[str, ...] = TABLES) -> list[tuple[str, list[dict[str, Any]]]]:
    leftovers: list[tuple[str, list[dict[str, Any]]]] = []
    for table in tables:
        rows = db.query(f"SELECT * FROM `{table}` LIMIT 10")
        if rows:
            leftovers.append((table, rows))
    return leftovers


def main() -> int:
    if config.db is None:
        print("No database configured; skipping leftover data check.")
        return 0
    db = DbClient(config.db)
    try:
        leftovers = find_leftovers(db)
    finally:
        db.close()
    if leftovers:
        print("Tests left data behind. Register cleanup for anything a test creates:", file=sys.stderr)
        for table, rows in leftovers:
            rendered = "\n    ".join(json.dumps(row, default=str) for row in rows)
            print(f"  {table}: {rendered}", file=sys.stderr)
        return 1
    print(f"No leftover test data in: {', '.join(TABLES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
