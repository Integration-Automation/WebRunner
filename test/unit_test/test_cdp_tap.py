import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from je_web_runner.utils.cdp_tap import (
    CdpRecorder,
    CdpReplayer,
    CdpTapError,
    load_recording,
)


class TestCdpRecorder(unittest.TestCase):

    def test_attach_records_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = MagicMock()
            driver.execute_cdp_cmd = MagicMock(return_value={"ok": True})
            recorder = CdpRecorder(output_path=Path(tmpdir) / "cdp.ndjson")
            original = recorder.attach(driver)
            driver.execute_cdp_cmd("Page.navigate", {"url": "https://x"})
            recorder.detach(driver, original)
            recorded = recorder.records()
            self.assertEqual(len(recorded), 1)
            self.assertEqual(recorded[0].method, "Page.navigate")
            self.assertEqual(recorded[0].return_value, {"ok": True})

    def test_record_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = MagicMock()
            driver.execute_cdp_cmd = MagicMock(side_effect=RuntimeError("boom"))
            recorder = CdpRecorder(output_path=Path(tmpdir) / "cdp.ndjson")
            original = recorder.attach(driver)
            with self.assertRaises(RuntimeError):
                driver.execute_cdp_cmd("Network.enable", {})
            recorder.detach(driver, original)
            self.assertIsNotNone(recorder.records()[0].error)

    def test_unsupported_driver(self):
        recorder = CdpRecorder(output_path="x.ndjson")
        with self.assertRaises(CdpTapError):
            recorder.attach(object())

    def test_flush_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = MagicMock()
            driver.execute_cdp_cmd = MagicMock(return_value="ok")
            path = Path(tmpdir) / "cdp.ndjson"
            recorder = CdpRecorder(output_path=path)
            original = recorder.attach(driver)
            driver.execute_cdp_cmd("Page.reload", {})
            driver.execute_cdp_cmd("Page.bringToFront", {})
            recorder.detach(driver, original)
            self.assertTrue(path.is_file())
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)

    def test_non_serialisable_return_repr_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = MagicMock()
            driver.execute_cdp_cmd = MagicMock(return_value=object())
            recorder = CdpRecorder(output_path=Path(tmpdir) / "cdp.ndjson")
            original = recorder.attach(driver)
            driver.execute_cdp_cmd("Custom.cmd", {})
            recorder.detach(driver, original)
            self.assertIsInstance(recorder.records()[0].return_value, str)


class TestLoadAndReplay(unittest.TestCase):

    def test_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            driver = MagicMock()
            driver.execute_cdp_cmd = MagicMock(return_value={"ok": True})
            path = Path(tmpdir) / "cdp.ndjson"
            recorder = CdpRecorder(output_path=path)
            original = recorder.attach(driver)
            driver.execute_cdp_cmd("Page.navigate", {"url": "https://x"})
            recorder.detach(driver, original)
            records = load_recording(path)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].method, "Page.navigate")

    def test_replayer_returns_recorded_values(self):
        replayer = CdpReplayer(records=[
            type("R", (), {
                "method": "A", "params": {}, "return_value": 1, "error": None,
                "timestamp": 0,
            })(),
            type("R", (), {
                "method": "B", "params": {}, "return_value": 2, "error": None,
                "timestamp": 0,
            })(),
        ])
        self.assertEqual(replayer.execute_cdp_cmd("A"), 1)
        self.assertEqual(replayer.execute_cdp_cmd("B"), 2)
        self.assertEqual(replayer.remaining(), 0)

    def test_replayer_drift_raises(self):
        replayer = CdpReplayer(records=[
            type("R", (), {
                "method": "A", "params": {}, "return_value": 1, "error": None,
                "timestamp": 0,
            })(),
        ])
        with self.assertRaises(CdpTapError):
            replayer.execute_cdp_cmd("B")

    def test_replay_exhausted(self):
        replayer = CdpReplayer(records=[])
        with self.assertRaises(CdpTapError):
            replayer.execute_cdp_cmd("A")

    def test_load_missing_file_raises(self):
        with self.assertRaises(CdpTapError):
            load_recording("does/not/exist.ndjson")


if __name__ == "__main__":
    unittest.main()
