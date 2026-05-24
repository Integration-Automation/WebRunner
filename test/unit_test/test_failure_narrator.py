"""Unit tests for je_web_runner.utils.failure_narrator."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.failure_narrator.narrator import (
    FailureBundle,
    FailureNarratorError,
    NarrationReport,
    build_prompt,
    load_bundle_dir,
    narrate,
    parse_response,
)


def _good_response(confidence="medium"):
    return json.dumps({
        "summary": "Login submit button was not visible.",
        "likely_cause": "Feature flag new_login_ui hid the button under this PR.",
        "next_step": "Toggle the flag off locally and re-run the suite.",
        "confidence": confidence,
    })


class StubClient:
    def __init__(self, response):
        self.response = response
        self.last_prompt = None

    def complete(self, prompt):
        self.last_prompt = prompt
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class TestFailureBundle(unittest.TestCase):

    def test_rejects_empty_test_id(self):
        with self.assertRaises(FailureNarratorError):
            FailureBundle(test_id="")


class TestLoadBundle(unittest.TestCase):

    def test_load_minimal(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = Path(tmp) / "t1"
            bundle_dir.mkdir()
            (bundle_dir / "meta.json").write_text(json.dumps({
                "test_id": "checkout/login.json",
                "action": "WR_click_element[id, submit]",
                "error_message": "Element not visible",
                "error_class": "ElementNotVisibleException",
                "last_url": "https://app/login",
                "failed_assertion": "Login form should be visible",
            }), encoding="utf-8")
            bundle = load_bundle_dir(bundle_dir)
            self.assertEqual(bundle.test_id, "checkout/login.json")
            self.assertEqual(bundle.error_class, "ElementNotVisibleException")

    def test_load_with_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_dir = Path(tmp) / "t"
            bundle_dir.mkdir()
            (bundle_dir / "meta.json").write_text(
                json.dumps({"test_id": "x"}), encoding="utf-8",
            )
            (bundle_dir / "console.log").write_text(
                "TypeError: foo\nWarning: bar\n", encoding="utf-8",
            )
            (bundle_dir / "network_errors.log").write_text(
                "500 /api/x\n", encoding="utf-8",
            )
            (bundle_dir / "dom.html").write_text("<div>x</div>", encoding="utf-8")
            bundle = load_bundle_dir(bundle_dir)
            self.assertEqual(len(bundle.console_errors), 2)
            self.assertEqual(len(bundle.network_errors), 1)
            self.assertIn("<div>x</div>", bundle.last_dom_excerpt)

    def test_missing_dir(self):
        with self.assertRaises(FailureNarratorError):
            load_bundle_dir("/no/such/dir")

    def test_missing_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FailureNarratorError):
                load_bundle_dir(tmp)

    def test_bad_meta_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "meta.json").write_text("not json", encoding="utf-8")
            with self.assertRaises(FailureNarratorError):
                load_bundle_dir(tmp)

    def test_bad_meta_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "meta.json").write_text(
                json.dumps([]), encoding="utf-8",
            )
            with self.assertRaises(FailureNarratorError):
                load_bundle_dir(tmp)


class TestBuildPrompt(unittest.TestCase):

    def test_includes_facts(self):
        prompt = build_prompt(FailureBundle(
            test_id="t1", action="click submit",
            error_message="boom", error_class="X",
        ))
        self.assertIn("t1", prompt)
        self.assertIn("click submit", prompt)
        self.assertIn("X: boom", prompt)

    def test_rejects_non_bundle(self):
        with self.assertRaises(FailureNarratorError):
            build_prompt("nope")  # type: ignore[arg-type]


class TestParseResponse(unittest.TestCase):

    def test_parses_clean(self):
        report = parse_response(_good_response())
        self.assertEqual(report.confidence, "medium")
        self.assertIn("button", report.summary)

    def test_extracts_from_surrounding_text(self):
        wrapped = "Here you go:\n" + _good_response() + "\nThanks!"
        self.assertEqual(parse_response(wrapped).confidence, "medium")

    def test_empty(self):
        with self.assertRaises(FailureNarratorError):
            parse_response("")

    def test_no_json(self):
        with self.assertRaises(FailureNarratorError):
            parse_response("text only no braces")

    def test_bad_json(self):
        with self.assertRaises(FailureNarratorError):
            parse_response("{not really json}")

    def test_non_dict(self):
        with self.assertRaises(FailureNarratorError):
            parse_response(json.dumps([1, 2, 3]))

    def test_missing_field(self):
        with self.assertRaises(FailureNarratorError):
            parse_response(json.dumps({
                "summary": "x", "likely_cause": "y", "next_step": "z",
                # confidence missing
            }))

    def test_bad_confidence(self):
        with self.assertRaises(FailureNarratorError):
            parse_response(_good_response(confidence="maybe"))


class TestNarrate(unittest.TestCase):

    def test_round_trip(self):
        client = StubClient(_good_response())
        report = narrate(FailureBundle(test_id="t1"), client)
        self.assertEqual(report.confidence, "medium")
        self.assertIn("t1", client.last_prompt)

    def test_client_error_wrapped(self):
        with self.assertRaises(FailureNarratorError):
            narrate(FailureBundle(test_id="t1"), StubClient(RuntimeError("rate")))


class TestNarrationReport(unittest.TestCase):

    def test_markdown(self):
        report = NarrationReport(
            summary="s", likely_cause="lc", next_step="ns", confidence="high",
        )
        md = report.markdown()
        self.assertIn("**Why this failed**: s", md)
        self.assertIn("(high)", md)


if __name__ == "__main__":
    unittest.main()
