"""Unit tests for je_web_runner.utils.multimodal_qa."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.multimodal_qa.qa import (
    MultimodalQaError,
    QaRequest,
    QaResponse,
    Verdict,
    VisionClient,
    ask,
    ask_path,
    assert_passes,
    build_prompt,
    parse_response,
)


class StubClient:
    def __init__(self, response):
        self.response = response
        self.last_prompt = None
        self.last_image = None

    def ask(self, prompt, image_b64):
        self.last_prompt = prompt
        self.last_image = image_b64
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _good_response(verdict="pass", confidence=0.9, rationale="looks fine", issues=None):
    return json.dumps({
        "verdict": verdict,
        "confidence": confidence,
        "rationale": rationale,
        "issues": issues or [],
    })


class TestRequest(unittest.TestCase):

    def test_rejects_empty_bytes(self):
        with self.assertRaises(MultimodalQaError):
            QaRequest(image_bytes=b"", question="Q")

    def test_rejects_non_bytes(self):
        with self.assertRaises(MultimodalQaError):
            QaRequest(image_bytes="not bytes", question="Q")  # type: ignore[arg-type]

    def test_rejects_blank_question(self):
        with self.assertRaises(MultimodalQaError):
            QaRequest(image_bytes=b"x", question="  ")

    def test_b64_image(self):
        req = QaRequest(image_bytes=b"hello", question="Q")
        self.assertEqual(req.b64_image(), "aGVsbG8=")


class TestBuildPrompt(unittest.TestCase):

    def test_includes_question(self):
        prompt = build_prompt(QaRequest(image_bytes=b"x", question="Is it red?"))
        self.assertIn("Is it red?", prompt)
        self.assertIn("verdict", prompt)

    def test_includes_rubric(self):
        prompt = build_prompt(QaRequest(
            image_bytes=b"x", question="Q",
            rubric=["button visible", "no overlap"],
        ))
        self.assertIn("Rubric", prompt)
        self.assertIn("button visible", prompt)


class TestParseResponse(unittest.TestCase):

    def test_parses_clean_pass(self):
        response = parse_response(_good_response())
        self.assertEqual(response.verdict, Verdict.PASS)
        self.assertEqual(response.confidence, 0.9)
        self.assertTrue(response.is_pass())

    def test_parses_fail_with_issues(self):
        raw = _good_response(verdict="fail", issues=["text cropped", "wrong color"])
        response = parse_response(raw)
        self.assertEqual(response.verdict, Verdict.FAIL)
        self.assertEqual(len(response.issues), 2)

    def test_extracts_from_surrounding_text(self):
        raw = "Sure thing! Here is the analysis:\n" + _good_response() + "\nLet me know."
        response = parse_response(raw)
        self.assertEqual(response.verdict, Verdict.PASS)

    def test_rejects_empty_response(self):
        with self.assertRaises(MultimodalQaError):
            parse_response("")

    def test_rejects_no_json(self):
        with self.assertRaises(MultimodalQaError):
            parse_response("no json here")

    def test_rejects_bad_json(self):
        with self.assertRaises(MultimodalQaError):
            parse_response("{not really json}")

    def test_rejects_unknown_verdict(self):
        raw = json.dumps({"verdict": "maybe", "confidence": 0.5, "rationale": "x"})
        with self.assertRaises(MultimodalQaError):
            parse_response(raw)

    def test_rejects_missing_confidence(self):
        raw = json.dumps({"verdict": "pass", "rationale": "x"})
        with self.assertRaises(MultimodalQaError):
            parse_response(raw)

    def test_clamps_confidence(self):
        raw = json.dumps({"verdict": "pass", "confidence": 5.0, "rationale": "x"})
        response = parse_response(raw)
        self.assertEqual(response.confidence, 1.0)

    def test_rejects_non_list_issues(self):
        raw = json.dumps({
            "verdict": "fail", "confidence": 0.5, "rationale": "x", "issues": "oops",
        })
        with self.assertRaises(MultimodalQaError):
            parse_response(raw)


class TestAsk(unittest.TestCase):

    def test_round_trip(self):
        client = StubClient(_good_response())
        response = ask(QaRequest(image_bytes=b"hi", question="Q?"), client)
        self.assertTrue(response.is_pass())
        self.assertIn("Q?", client.last_prompt)
        self.assertEqual(client.last_image, "aGk=")

    def test_client_error_wrapped(self):
        client = StubClient(RuntimeError("rate limit"))
        with self.assertRaises(MultimodalQaError):
            ask(QaRequest(image_bytes=b"x", question="Q"), client)


class TestAskPath(unittest.TestCase):

    def test_reads_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "shot.png"
            p.write_bytes(b"\x89PNG")
            client = StubClient(_good_response())
            response = ask_path(p, "ok?", client)
            self.assertTrue(response.is_pass())

    def test_missing_file(self):
        with self.assertRaises(MultimodalQaError):
            ask_path("/no/such/file.png", "Q", StubClient(_good_response()))


class TestAssertPasses(unittest.TestCase):

    def test_pass(self):
        assert_passes(parse_response(_good_response()))

    def test_fail(self):
        with self.assertRaises(MultimodalQaError):
            assert_passes(parse_response(_good_response(verdict="fail")))

    def test_pass_low_confidence_fails(self):
        with self.assertRaises(MultimodalQaError):
            assert_passes(
                parse_response(_good_response(confidence=0.2)),
                min_confidence=0.5,
            )

    def test_bad_min_confidence(self):
        with self.assertRaises(MultimodalQaError):
            assert_passes(parse_response(_good_response()), min_confidence=2.0)

    def test_rejects_non_response(self):
        with self.assertRaises(MultimodalQaError):
            assert_passes("not a response")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
