"""MySQL client for database assertions.

Connection settings come from config.db (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME).
Always use parameterized queries: pass values in `params`, never interpolate them into SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from config import DbConfig
from utils.logger import create_logger

log = create_logger("db")


@dataclass(frozen=True)
class WriteResult:
    insert_id: int
    affected_rows: int


class DbClient:
    def __init__(self, db_config: DbConfig | None) -> None:
        if db_config is None:
            raise RuntimeError("Database is not configured. Set DB_HOST, DB_USER, DB_PASSWORD and DB_NAME.")
        self._config = db_config
        self._connections: list[Connection[DictCursor]] = []

    def _connect(self) -> Connection[DictCursor]:
        connection: Connection[DictCursor] = pymysql.connect(
            host=self._config.host,
            port=self._config.port,
            user=self._config.user or "",
            password=self._config.password or "",
            database=self._config.database or "",
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )
        self._connections.append(connection)
        return connection

    def query(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        log["debug"](f"{sql} {params}")
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            return list(rows)
        finally:
            connection.close()
            self._connections.remove(connection)

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> WriteResult:
        log["debug"](f"{sql} {params}")
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return WriteResult(insert_id=int(cursor.lastrowid or 0), affected_rows=int(cursor.rowcount))
        finally:
            connection.close()
            self._connections.remove(connection)

    def one(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def count(self, table: str, where: str = "1 = 1", params: list[Any] | tuple[Any, ...] = ()) -> int:
        """Return the number of rows in `table` matching an optional WHERE clause."""
        if not table.isidentifier() or not table.replace("_", "").isalnum():
            raise ValueError(f"Invalid table name: {table}")
        row = self.one(f"SELECT COUNT(*) AS total FROM `{table}` WHERE {where}", params)
        total = 0 if row is None else row.get("total", 0)
        return int(total)

    def close(self) -> None:
        for connection in self._connections:
            connection.close()
        self._connections.clear()
