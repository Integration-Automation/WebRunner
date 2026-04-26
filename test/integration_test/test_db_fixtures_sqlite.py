"""
Integration: load_into_connection against a real in-memory SQLite database.

Verifies the fixture loader's identifier validation + SQL building works
end-to-end through SQLAlchemy, not just against a mock execute() spy.
"""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.database.fixtures import (
    DbFixtureError,
    load_fixture_file,
    load_into_connection,
    truncate_tables,
)


def _has_sqlalchemy() -> bool:
    try:
        import sqlalchemy  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_has_sqlalchemy(), "sqlalchemy not installed")
class TestDbFixturesSqlite(unittest.TestCase):

    def setUp(self):
        from sqlalchemy import create_engine, text
        self._engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        self._text = text
        with self._engine.connect() as conn:
            conn.execute(self._text("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0
                )
            """))
            conn.commit()

    def test_load_into_real_sqlite(self):
        fixture = {
            "users": [
                {"id": 1, "name": "Alice", "is_admin": 1},
                {"id": 2, "name": "Bob", "is_admin": 0},
            ]
        }
        with self._engine.begin() as conn:
            counts = load_into_connection(conn, fixture)
        self.assertEqual(counts, {"users": 2})

        with self._engine.connect() as conn:
            rows = conn.execute(
                self._text("SELECT name, is_admin FROM users ORDER BY id")
            ).fetchall()
        self.assertEqual([(r[0], r[1]) for r in rows],
                         [("Alice", 1), ("Bob", 0)])

    def test_truncate_tables_real(self):
        fixture = {"users": [{"id": 1, "name": "x", "is_admin": 0}]}
        with self._engine.begin() as conn:
            load_into_connection(conn, fixture)
            truncate_tables(conn, ["users"])
            count = conn.execute(self._text("SELECT COUNT(*) FROM users")).scalar()
        self.assertEqual(count, 0)

    def test_unsafe_table_name_blocked_before_sql(self):
        with self._engine.connect() as conn:
            with self.assertRaises(DbFixtureError):
                load_into_connection(conn, {"users; DROP TABLE users;--": [{"id": 1}]})

    def test_round_trip_via_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "seed.json"
            path.write_text(json.dumps({
                "users": [{"id": 99, "name": "Carol", "is_admin": 0}]
            }), encoding="utf-8")
            fixture = load_fixture_file(path)
            with self._engine.begin() as conn:
                load_into_connection(conn, fixture)
            with self._engine.connect() as conn:
                row = conn.execute(
                    self._text("SELECT name FROM users WHERE id = 99")
                ).fetchone()
            self.assertEqual(row[0], "Carol")


if __name__ == "__main__":
    unittest.main()
