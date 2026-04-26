import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from je_web_runner.utils.database.fixtures import (
    DbFixtureError,
    load_fixture_file,
    load_into_connection,
    truncate_tables,
    validate_shape,
)


class TestValidateShape(unittest.TestCase):

    def test_round_trip(self):
        data = {"users": [{"id": 1, "name": "Alice"}]}
        self.assertEqual(validate_shape(data), data)

    def test_root_must_be_object(self):
        with self.assertRaises(DbFixtureError):
            validate_shape([])

    def test_rows_must_be_list(self):
        with self.assertRaises(DbFixtureError):
            validate_shape({"t": "not a list"})

    def test_row_must_be_object(self):
        with self.assertRaises(DbFixtureError):
            validate_shape({"t": [["row-as-list"]]})

    def test_unsupported_value_type(self):
        with self.assertRaises(DbFixtureError):
            validate_shape({"t": [{"k": object()}]})


class TestLoadFile(unittest.TestCase):

    def test_loads_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = Path(tmpdir) / "fixture.json"
            fp.write_text(json.dumps({"t": [{"a": 1}]}), encoding="utf-8")
            self.assertEqual(load_fixture_file(fp)["t"][0]["a"], 1)

    def test_missing_file_raises(self):
        with self.assertRaises(DbFixtureError):
            load_fixture_file("nope.json")

    def test_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = Path(tmpdir) / "fixture.json"
            fp.write_text("not json", encoding="utf-8")
            with self.assertRaises(DbFixtureError):
                load_fixture_file(fp)


class TestLoadIntoConnection(unittest.TestCase):

    def test_inserts_all_rows(self):
        connection = MagicMock()
        result = load_into_connection(connection, {"users": [
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
        ]})
        self.assertEqual(result, {"users": 2})
        # Each row triggers one execute call
        self.assertEqual(connection.execute.call_count, 2)

    def test_only_tables_filters(self):
        connection = MagicMock()
        result = load_into_connection(
            connection,
            {"users": [{"id": 1}], "logs": [{"id": 2}]},
            only_tables=["users"],
        )
        self.assertEqual(result, {"users": 1})

    def test_unsupported_connection(self):
        with self.assertRaises(DbFixtureError):
            load_into_connection(object(), {"t": [{"a": 1}]})


class TestTruncate(unittest.TestCase):

    def test_truncate_dispatches_per_table(self):
        connection = MagicMock()
        truncate_tables(connection, ["users", "logs"])
        self.assertEqual(connection.execute.call_count, 2)


if __name__ == "__main__":
    unittest.main()
