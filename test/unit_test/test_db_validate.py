import os
import tempfile
import unittest

from je_web_runner.utils.database.db_validate import (
    DatabaseValidationError,
    db_assert_count,
    db_assert_empty,
    db_assert_exists,
    db_assert_value,
    db_query,
)


def _seed_sqlite(path: str) -> str:
    import sqlite3
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT);
            INSERT INTO users (name, email) VALUES
              ('alice', 'alice@example.com'),
              ('bob',   'bob@example.com');
            """
        )
        conn.commit()
    finally:
        conn.close()
    return f"sqlite:///{path}"


class TestDbValidate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls._db_path = os.path.join(cls._dir.name, "test.db")
        cls._url = _seed_sqlite(cls._db_path)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def test_query_returns_rows_as_dicts(self):
        rows = db_query(self._url, "SELECT name, email FROM users ORDER BY name")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "alice")

    def test_query_with_bound_params(self):
        rows = db_query(
            self._url,
            "SELECT name FROM users WHERE name = :name",
            params={"name": "bob"},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "bob")

    def test_assert_count_ok(self):
        db_assert_count(self._url, "SELECT 1 FROM users", expected=2)

    def test_assert_count_mismatch(self):
        with self.assertRaises(DatabaseValidationError):
            db_assert_count(self._url, "SELECT 1 FROM users", expected=99)

    def test_assert_value_matches(self):
        db_assert_value(
            self._url,
            "SELECT name FROM users WHERE name = :name",
            column="name",
            expected="alice",
            params={"name": "alice"},
        )

    def test_assert_value_mismatch(self):
        with self.assertRaises(DatabaseValidationError):
            db_assert_value(
                self._url,
                "SELECT name FROM users WHERE name = :name",
                column="name",
                expected="charlie",
                params={"name": "alice"},
            )

    def test_assert_exists(self):
        db_assert_exists(
            self._url,
            "SELECT 1 FROM users WHERE email LIKE :pattern",
            params={"pattern": "%example.com"},
        )

    def test_assert_empty(self):
        db_assert_empty(
            self._url,
            "SELECT 1 FROM users WHERE name = :name",
            params={"name": "absent"},
        )


if __name__ == "__main__":
    unittest.main()
