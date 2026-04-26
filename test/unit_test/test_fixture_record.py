import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.snapshot.fixture_record import (
    FixtureRecorder,
    FixtureRecorderError,
    RecorderMode,
    open_recorder,
)


class TestRecorder(unittest.TestCase):

    def test_auto_records_then_replays(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fx.json"
            calls = {"n": 0}

            def producer():
                calls["n"] += 1
                return {"random": calls["n"]}

            recorder = FixtureRecorder(path, mode=RecorderMode.AUTO)
            first = recorder.replay_or_record("k", producer)
            second = FixtureRecorder(path, mode=RecorderMode.AUTO).replay_or_record(
                "k", producer
            )
            self.assertEqual(first, {"random": 1})
            self.assertEqual(second, {"random": 1})
            self.assertEqual(calls["n"], 1)

    def test_record_overrides_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fx.json"
            FixtureRecorder(path, mode=RecorderMode.AUTO).replay_or_record(
                "k", lambda: "first"
            )
            FixtureRecorder(path, mode=RecorderMode.RECORD).replay_or_record(
                "k", lambda: "second"
            )
            self.assertEqual(json.loads(path.read_text())["k"], "second")

    def test_replay_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fx.json"
            recorder = FixtureRecorder(path, mode=RecorderMode.REPLAY)
            with self.assertRaises(FixtureRecorderError):
                recorder.replay_or_record("k", lambda: "ignored")

    def test_invalid_recorder_file_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "fx.json"
            path.write_text("not json", encoding="utf-8")
            with self.assertRaises(FixtureRecorderError):
                FixtureRecorder(path).has("k")

    def test_open_recorder_string_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = open_recorder(Path(tmpdir) / "fx.json", "record")
            self.assertEqual(recorder.mode, RecorderMode.RECORD)

    def test_open_recorder_unknown_mode(self):
        with self.assertRaises(FixtureRecorderError):
            open_recorder("x.json", "ghost-mode")


if __name__ == "__main__":
    unittest.main()
