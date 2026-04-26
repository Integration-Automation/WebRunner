r"""
資料庫 fixture 載入器：從 dict / JSON 把 ``{table: [rows]}`` 寫進 SQLAlchemy 連線。
DB fixture loader. Reads a fixture file or in-memory dict shaped as
``{"table_name": [{column: value}, ...]}`` and ``INSERT``\ s the rows
into the supplied SQLAlchemy ``Connection``.

Designed to seed testcontainers Postgres / MySQL / SQLite without pulling
in heavyweight ORM models.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DbFixtureError(WebRunnerException):
    """Raised when a fixture file or shape is invalid."""


_AllowedScalar = (str, int, float, bool, type(None))
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_identifier(name: str, kind: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise DbFixtureError(f"{kind} {name!r} contains unsafe characters")
    return name


def load_fixture_file(path: Union[str, Path]) -> Dict[str, List[Dict[str, Any]]]:
    """Read a JSON fixture file and validate its shape."""
    fp = Path(path)
    if not fp.is_file():
        raise DbFixtureError(f"fixture file not found: {path!r}")
    try:
        data = json.loads(fp.read_text(encoding="utf-8"))
    except ValueError as error:
        raise DbFixtureError(f"fixture not valid JSON: {error}") from error
    return validate_shape(data)


def validate_shape(data: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Make sure the loaded object matches ``{table: [rows]}``."""
    if not isinstance(data, dict):
        raise DbFixtureError("fixture root must be an object")
    return {
        table: _validate_rows(table, rows)
        for table, rows in _validated_tables(data)
    }


def _validated_tables(data: Dict[Any, Any]):
    for table, rows in data.items():
        if not isinstance(table, str) or not table:
            raise DbFixtureError(f"table name must be non-empty string, got {table!r}")
        if not isinstance(rows, list):
            raise DbFixtureError(f"rows for {table!r} must be a list")
        yield table, rows


def _validate_rows(table: str, rows: List[Any]) -> List[Dict[str, Any]]:
    validated: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise DbFixtureError(
                f"{table!r} row {index} must be an object, got {type(row).__name__}"
            )
        for column, value in row.items():
            if not isinstance(value, _AllowedScalar):
                raise DbFixtureError(
                    f"{table!r}.{column}: unsupported type {type(value).__name__}"
                )
        validated.append(row)
    return validated


def load_into_connection(
    connection: Any,
    fixture: Dict[str, List[Dict[str, Any]]],
    quote: str = '"',
    only_tables: Optional[Sequence[str]] = None,
) -> Dict[str, int]:
    """
    對每個表 batch insert 所有 rows，回傳 ``{table: rows_inserted}``
    Insert every fixture row using ``INSERT INTO <t> (...) VALUES (...)``
    with bound parameters. Returns the count of rows inserted per table.
    """
    if not hasattr(connection, "execute"):
        raise DbFixtureError("connection must expose execute() (SQLAlchemy or PEP-249)")
    inserted: Dict[str, int] = {}
    allowed = set(only_tables) if only_tables else None
    for table, rows in fixture.items():
        if allowed is not None and table not in allowed:
            continue
        if not rows:
            continue
        safe_table = _safe_identifier(table, "table")
        columns = [_safe_identifier(c, "column") for c in rows[0].keys()]
        placeholder = ", ".join(f":{col}" for col in columns)
        column_text = ", ".join(f"{quote}{col}{quote}" for col in columns)
        # nosemgrep: python_sql_rule-hardcoded-sql-expression
        sql = (  # nosec B608 — identifiers validated above
            f"INSERT INTO {quote}{safe_table}{quote} "
            f"({column_text}) VALUES ({placeholder})"
        )
        for row in rows:
            connection.execute(_wrap_text(sql), row)
        inserted[table] = len(rows)
        web_runner_logger.info(f"db_fixtures inserted {len(rows)} into {table!r}")
    return inserted


def _wrap_text(sql: str) -> Any:
    """Use SQLAlchemy ``text()`` when available, otherwise return raw SQL."""
    try:
        from sqlalchemy import text  # type: ignore[import-not-found]
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        return text(sql)
    except Exception:  # pylint: disable=broad-except
        return sql


def truncate_tables(connection: Any, tables: Iterable[str], quote: str = '"') -> None:
    """``DELETE FROM`` each table; cheap teardown for in-test fixture reload."""
    for table in tables:
        safe_table = _safe_identifier(table, "table")
        # nosemgrep: python_sql_rule-hardcoded-sql-expression
        connection.execute(  # nosec B608 — identifier validated above
            _wrap_text(f"DELETE FROM {quote}{safe_table}{quote}"), {},
        )
