"""Unit tests for je_web_runner.utils.session_to_test."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.session_to_test.converter import (
    ConversionResult,
    ConversionStats,
    SessionToTestError,
    convert_events,
    convert_generic_events,
    convert_rrweb_events,
    write_actions_json,
)


def _rrweb_meta(href):
    return {"type": 4, "timestamp": 0, "data": {"href": href, "width": 1280, "height": 720}}


def _rrweb_click(node_id, ts=1000):
    return {"type": 3, "timestamp": ts, "data": {"source": 2, "type": 2, "id": node_id}}


def _rrweb_input(node_id, text, ts=2000):
    return {"type": 3, "timestamp": ts, "data": {"source": 5, "id": node_id, "text": text}}


def _rrweb_scroll(x, y, ts=3000):
    return {"type": 3, "timestamp": ts, "data": {"source": 3, "x": x, "y": y}}


class TestRrweb(unittest.TestCase):

    def test_meta_to_navigate(self):
        result = convert_rrweb_events([
            _rrweb_meta("https://example.com"),
            _rrweb_click(7),
        ])
        self.assertEqual(result.actions[0], {"WR_to_url": ["https://example.com"]})
        self.assertEqual(result.actions[1]["WR_click_element"][0], "css selector")
        self.assertIn("data-rrweb-id", result.actions[1]["WR_click_element"][1])

    def test_input_event(self):
        result = convert_rrweb_events([
            _rrweb_meta("https://x"),
            _rrweb_input(3, "hello"),
        ])
        self.assertEqual(
            result.actions[1],
            {"WR_input_to_element": ["css selector", '[data-rrweb-id="3"]', "hello"]},
        )

    def test_scroll_becomes_comment(self):
        result = convert_rrweb_events([
            _rrweb_meta("https://x"),
            _rrweb_scroll(0, 500),
        ])
        self.assertEqual(result.actions[1], {"WR_comment": ["scroll to 0,500"]})

    def test_full_snapshot_skipped(self):
        result = convert_rrweb_events([
            _rrweb_meta("https://x"),
            {"type": 2, "timestamp": 0, "data": {}},
            _rrweb_click(1),
        ])
        self.assertEqual(result.stats.actions_emitted, 2)
        self.assertGreaterEqual(result.stats.skipped_events, 1)

    def test_mouse_without_id_skipped(self):
        result = convert_rrweb_events([
            _rrweb_meta("https://x"),
            {"type": 3, "timestamp": 1, "data": {"source": 2, "type": 2}},
            _rrweb_click(1),
        ])
        # Only meta + valid click → 2 actions
        self.assertEqual(result.stats.actions_emitted, 2)
        self.assertGreaterEqual(result.stats.skipped_events, 1)

    def test_empty_emits_error(self):
        with self.assertRaises(SessionToTestError):
            convert_rrweb_events([])

    def test_unknown_event_type_skipped(self):
        result = convert_rrweb_events([
            _rrweb_meta("https://x"),
            {"type": 99, "timestamp": 0, "data": {}},
        ])
        self.assertGreaterEqual(result.stats.skipped_events, 1)

    def test_meta_without_href_skipped(self):
        with self.assertRaises(SessionToTestError):
            convert_rrweb_events([
                {"type": 4, "timestamp": 0, "data": {}},
            ])

    def test_non_list_rejected(self):
        with self.assertRaises(SessionToTestError):
            convert_rrweb_events({"not": "a list"})  # type: ignore[arg-type]


class TestGeneric(unittest.TestCase):

    def test_navigate(self):
        result = convert_generic_events([
            {"kind": "navigate", "url": "https://x", "timestamp": 0},
        ])
        self.assertEqual(result.actions[0], {"WR_to_url": ["https://x"]})

    def test_click_with_dict_target(self):
        result = convert_generic_events([
            {"kind": "click", "target": {"by": "id", "value": "submit"}},
        ])
        self.assertEqual(result.actions[0], {"WR_click_element": ["id", "submit"]})

    def test_click_with_string_target(self):
        result = convert_generic_events([
            {"kind": "click", "target": "#submit"},
        ])
        self.assertEqual(result.actions[0], {"WR_click_element": ["css selector", "#submit"]})

    def test_input_value(self):
        result = convert_generic_events([
            {"kind": "input", "target": "#name", "value": "alice"},
        ])
        self.assertEqual(
            result.actions[0],
            {"WR_input_to_element": ["css selector", "#name", "alice"]},
        )

    def test_submit_with_and_without_target(self):
        result = convert_generic_events([
            {"kind": "submit", "target": "#form"},
            {"kind": "submit"},
        ])
        self.assertEqual(result.actions[0], {"WR_submit_element": ["css selector", "#form"]})
        self.assertEqual(result.actions[1], {"WR_comment": ["submit form (no target)"]})

    def test_wait(self):
        result = convert_generic_events([{"kind": "wait", "seconds": 1.5}])
        self.assertEqual(result.actions[0], {"WR_implicitly_wait": [1.5]})

    def test_wait_bad_seconds_skipped(self):
        with self.assertRaises(SessionToTestError):
            convert_generic_events([{"kind": "wait", "seconds": "soon"}])

    def test_unknown_kind_skipped(self):
        with self.assertRaises(SessionToTestError):
            convert_generic_events([{"kind": "wat"}])


class TestAutoDetect(unittest.TestCase):

    def test_rrweb_detected_by_int_type(self):
        events = [_rrweb_meta("https://x"), _rrweb_click(1)]
        result = convert_events(events)
        self.assertEqual(result.actions[0], {"WR_to_url": ["https://x"]})

    def test_generic_detected(self):
        result = convert_events([{"kind": "navigate", "url": "https://x"}])
        self.assertEqual(result.actions[0], {"WR_to_url": ["https://x"]})

    def test_empty_rejected(self):
        with self.assertRaises(SessionToTestError):
            convert_events([])


class TestFromFile(unittest.TestCase):

    def test_load_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ev.json"
            path.write_text(json.dumps([
                {"kind": "navigate", "url": "https://x"},
            ]), encoding="utf-8")
            result = convert_events(path)
            self.assertEqual(result.actions[0], {"WR_to_url": ["https://x"]})

    def test_load_file_with_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ev.json"
            path.write_text(json.dumps({"events": [
                {"kind": "navigate", "url": "https://x"},
            ]}), encoding="utf-8")
            result = convert_events(path)
            self.assertEqual(len(result.actions), 1)

    def test_missing_file(self):
        with self.assertRaises(SessionToTestError):
            convert_events("/no/such.json")

    def test_bad_payload_type(self):
        with self.assertRaises(SessionToTestError):
            convert_events(123)  # type: ignore[arg-type]


class TestWriteActions(unittest.TestCase):

    def test_write(self):
        result = ConversionResult(
            actions=[{"WR_to_url": ["https://x"]}],
            stats=ConversionStats(input_events=1, actions_emitted=1),
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = write_actions_json(result, Path(tmp) / "actions.json")
            self.assertEqual(
                json.loads(out.read_text(encoding="utf-8")),
                [{"WR_to_url": ["https://x"]}],
            )


if __name__ == "__main__":
    unittest.main()
