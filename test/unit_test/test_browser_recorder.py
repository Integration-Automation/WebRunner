import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.recorder.browser_recorder import (
    RecorderError,
    events_to_actions,
    pull_events,
    save_recording,
    start_recording,
    stop_recording,
)


class _FakeWrapper:
    """Mimics WebDriverWrapper exposing current_webdriver."""

    def __init__(self, driver):
        self.current_webdriver = driver


class TestRecorderInjection(unittest.TestCase):

    def test_start_recording_executes_install_script(self):
        driver = MagicMock()
        start_recording(_FakeWrapper(driver))
        driver.execute_script.assert_called_once()
        self.assertIn("__wr_recorder_installed", driver.execute_script.call_args[0][0])

    def test_pull_events_returns_event_list(self):
        driver = MagicMock()
        driver.execute_script.return_value = [{"type": "click", "selector": "#go"}]
        events = pull_events(_FakeWrapper(driver))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["selector"], "#go")

    def test_pull_events_handles_none(self):
        driver = MagicMock()
        driver.execute_script.return_value = None
        self.assertEqual(pull_events(_FakeWrapper(driver)), [])

    def test_pull_events_rejects_unexpected_payload(self):
        driver = MagicMock()
        driver.execute_script.return_value = "not a list"
        with self.assertRaises(RecorderError):
            pull_events(_FakeWrapper(driver))

    def test_stop_recording_clears_flag(self):
        driver = MagicMock()
        stop_recording(_FakeWrapper(driver))
        script = driver.execute_script.call_args[0][0]
        self.assertIn("__wr_recorder_installed = false", script)

    def test_resolve_driver_rejects_unsupported_object(self):
        with self.assertRaises(RecorderError):
            start_recording(object())


class TestEventTranslation(unittest.TestCase):

    def test_click_translates_to_save_find_click_triplet(self):
        actions = events_to_actions([{"type": "click", "selector": "#submit"}])
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0][0], "WR_SaveTestObject")
        self.assertEqual(actions[0][1]["test_object_name"], "#submit")
        self.assertEqual(actions[0][1]["object_type"], "CSS_SELECTOR")
        self.assertEqual(actions[1][0], "WR_find_element")
        self.assertEqual(actions[2][0], "WR_left_click")

    def test_input_translates_with_value(self):
        actions = events_to_actions([
            {"type": "input", "selector": "input[name=\"q\"]", "value": "hello"}
        ])
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[2][0], "WR_input_to_element")
        self.assertEqual(actions[2][1]["input_value"], "hello")

    def test_unknown_event_type_is_skipped(self):
        actions = events_to_actions([
            {"type": "scroll", "selector": "#x"},
            {"type": "click", "selector": "#go"},
        ])
        self.assertEqual(len(actions), 3)


class TestSaveRecording(unittest.TestCase):

    def test_save_recording_writes_action_json(self):
        driver = MagicMock()
        driver.execute_script.return_value = [
            {"type": "click", "selector": "#go"},
            {"type": "input", "selector": "#q", "value": "hi"},
        ]
        wrapper = _FakeWrapper(driver)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "rec.json")
            raw = os.path.join(tmpdir, "raw.json")
            save_recording(wrapper, output, raw)
            self.assertTrue(os.path.exists(output))
            self.assertTrue(os.path.exists(raw))
            with open(output, encoding="utf-8") as out_file:
                actions = json.load(out_file)
            self.assertEqual(actions[0][0], "WR_SaveTestObject")
            self.assertEqual(len(actions), 6)


if __name__ == "__main__":
    unittest.main()
