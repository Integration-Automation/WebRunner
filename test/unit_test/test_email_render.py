"""Unit tests for je_web_runner.utils.email_render."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.email_render.render import (
    DEFAULT_VIEWPORTS,
    CapturedEmail,
    EmailRenderError,
    RenderArtifact,
    ViewportProfile,
    assert_subject_contains,
    export_summary_json,
    load_eml_dir,
    load_eml_file,
    render_email_in_viewports,
)


def _write_eml(path: Path, *, subject="Hello", html="<h1>Hi</h1>", to="user@example.com"):
    raw = (
        f"From: noreply@example.com\r\n"
        f"To: {to}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: <{path.stem}@test>\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n\r\n"
        f"{html}\r\n"
    )
    path.write_bytes(raw.encode("utf-8"))


class TestEmlLoading(unittest.TestCase):

    def test_load_single_eml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.eml"
            _write_eml(path, subject="Welcome!", html="<p>Body</p>")
            captured = load_eml_file(path)
            self.assertEqual(captured.subject, "Welcome!")
            self.assertEqual(captured.to, ["user@example.com"])
            self.assertTrue(captured.has_html())
            self.assertIn("<p>Body</p>", captured.html_body or "")

    def test_load_missing_file_raises(self):
        with self.assertRaises(EmailRenderError):
            load_eml_file("/no/such/file.eml")

    def test_load_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_eml(Path(tmp) / "a.eml", subject="A")
            _write_eml(Path(tmp) / "b.eml", subject="B")
            (Path(tmp) / "ignore.txt").write_text("not eml")
            captured = load_eml_dir(tmp)
            self.assertEqual([c.subject for c in captured], ["A", "B"])

    def test_load_dir_missing_raises(self):
        with self.assertRaises(EmailRenderError):
            load_eml_dir("/no/such/dir")


class TestMultipart(unittest.TestCase):

    def test_multipart_extracts_html_and_text(self):
        raw = (
            "From: a@x.com\r\nTo: b@x.com\r\nSubject: Mixed\r\n"
            "Message-ID: <mp@test>\r\n"
            'Content-Type: multipart/alternative; boundary="BOUND"\r\n\r\n'
            "--BOUND\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nplain body\r\n"
            "--BOUND\r\nContent-Type: text/html; charset=utf-8\r\n\r\n<p>html body</p>\r\n"
            "--BOUND--\r\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.eml"
            path.write_bytes(raw.encode("utf-8"))
            captured = load_eml_file(path)
            self.assertIn("<p>html body</p>", captured.html_body or "")
            self.assertIn("plain body", captured.text_body or "")


class TestRendering(unittest.TestCase):

    def test_render_calls_driver_for_each_viewport(self):
        captured = CapturedEmail(
            message_id="m1", subject="S", from_addr="x", to=["y"],
            html_body="<p>hi</p>",
        )
        calls = []

        def driver(html, viewport, target):
            self.assertIn("<p>hi</p>", html)
            target.write_bytes(b"\x89PNG fake")
            calls.append(viewport.name)
            return target

        with tempfile.TemporaryDirectory() as tmp:
            artifacts = render_email_in_viewports(captured, driver, tmp)
            self.assertEqual(len(artifacts), len(DEFAULT_VIEWPORTS))
            self.assertEqual(calls, [v.name for v in DEFAULT_VIEWPORTS])
            for art in artifacts:
                self.assertTrue(art.screenshot_path.exists())
                self.assertIsInstance(art, RenderArtifact)

    def test_render_skips_when_no_html(self):
        captured = CapturedEmail(
            message_id="m2", subject="S", from_addr="x", to=["y"], html_body=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(EmailRenderError):
                render_email_in_viewports(captured, lambda *a: Path(tmp), tmp)

    def test_custom_viewports(self):
        captured = CapturedEmail(
            message_id="m3", subject="S", from_addr="x", to=["y"], html_body="<p>x</p>",
        )

        def driver(html, viewport, target):
            target.write_bytes(b"\x89PNG")
            return target

        custom = (ViewportProfile("tiny", 100, 200),)
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = render_email_in_viewports(captured, driver, tmp, viewports=custom)
            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0].viewport, "tiny")
            self.assertEqual(artifacts[0].width, 100)


class TestAssertions(unittest.TestCase):

    def test_subject_contains_pass(self):
        captured = CapturedEmail(
            message_id="m", subject="Order #1234 confirmed",
            from_addr="x", to=["y"],
        )
        assert_subject_contains(captured, "#1234")

    def test_subject_contains_fail(self):
        captured = CapturedEmail(
            message_id="m", subject="Order confirmed",
            from_addr="x", to=["y"],
        )
        with self.assertRaises(EmailRenderError):
            assert_subject_contains(captured, "#9999")

    def test_subject_contains_rejects_empty(self):
        captured = CapturedEmail(message_id="m", subject="", from_addr="x", to=["y"])
        with self.assertRaises(EmailRenderError):
            assert_subject_contains(captured, "")


class TestSummary(unittest.TestCase):

    def test_export_summary_json(self):
        captures = [
            CapturedEmail(message_id="m1", subject="A", from_addr="x", to=["a"], html_body="<p/>"),
            CapturedEmail(message_id="m2", subject="B", from_addr="y", to=["b"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = export_summary_json(captures, Path(tmp) / "out.json")
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 2)
            self.assertTrue(data[0]["has_html"])
            self.assertFalse(data[1]["has_html"])


if __name__ == "__main__":
    unittest.main()
