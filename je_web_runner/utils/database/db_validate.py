"""
資料庫驗證工具：透過 SQLAlchemy 連到後端，斷言查詢結果。
Database validation helpers via SQLAlchemy. Lets action JSON confirm that a
UI flow really wrote to the backing store.

``sqlalchemy`` 為軟相依。
``sqlalchemy`` is a soft dependency.

安全 / Security:
- 一律以 bound parameter 傳值，不做字串拼接（避免 SQL injection）。
  All values pass through bound parameters; no string concatenation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class DatabaseValidationError(WebRunnerException):
    """Raised when SQLAlchemy is missing, the query fails, or an assertion is violated."""


def _require_sqlalchemy():
    try:
        from sqlalchemy import create_engine, text  # type: ignore[import-not-found]
        return create_engine, text
    except ImportError as error:
        raise DatabaseValidationError(
            "sqlalchemy is not installed. Install with: pip install sqlalchemy"
        ) from error


def db_query(
    connection_url: str,
    sql: str,
    params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    對 ``connection_url`` 執行帶 bound params 的 SQL，回傳結果（list of dict）
    Run a parameterised SQL statement against ``connection_url`` and return
    the rows as a list of dicts (column → value).
    """
    web_runner_logger.info(f"db_query against {connection_url!r}")
    create_engine, text = _require_sqlalchemy()
    engine = create_engine(connection_url)
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql), params or {})
            keys = list(result.keys())
            return [dict(zip(keys, row)) for row in result.fetchall()]
    finally:
        engine.dispose()


def db_assert_count(
    connection_url: str,
    sql: str,
    expected: int,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """斷言 SQL 回傳列數等於 ``expected``。"""
    rows = db_query(connection_url, sql, params=params)
    if len(rows) != int(expected):
        raise DatabaseValidationError(
            f"db_assert_count expected {expected} rows, got {len(rows)}"
        )


def db_assert_value(
    connection_url: str,
    sql: str,
    column: str,
    expected: Any,
    row_index: int = 0,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """斷言指定列、指定欄位的值等於 ``expected``。"""
    rows = db_query(connection_url, sql, params=params)
    if not rows:
        raise DatabaseValidationError("db_assert_value: query returned no rows")
    if row_index < 0 or row_index >= len(rows):
        raise DatabaseValidationError(
            f"db_assert_value: row_index {row_index} out of range (got {len(rows)} rows)"
        )
    if column not in rows[row_index]:
        raise DatabaseValidationError(
            f"db_assert_value: column {column!r} not in row keys "
            f"{list(rows[row_index].keys())}"
        )
    actual = rows[row_index][column]
    if actual != expected:
        raise DatabaseValidationError(
            f"db_assert_value: column {column!r} expected {expected!r}, got {actual!r}"
        )


def db_assert_exists(
    connection_url: str,
    sql: str,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """斷言查詢回傳至少一列。"""
    rows = db_query(connection_url, sql, params=params)
    if not rows:
        raise DatabaseValidationError("db_assert_exists: query returned no rows")


def db_assert_empty(
    connection_url: str,
    sql: str,
    params: Optional[Dict[str, Any]] = None,
) -> None:
    """斷言查詢沒有任何結果。"""
    rows = db_query(connection_url, sql, params=params)
    if rows:
        raise DatabaseValidationError(
            f"db_assert_empty: expected 0 rows, got {len(rows)}"
        )
