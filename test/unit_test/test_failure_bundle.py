import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.failure_bundle import (
    FailureBundle,
    FailureBundleError,
    extract_bundle,
)


class TestFailureBundle(unittest.TestCase):

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle = FailureBundle(test_name="login_test", error_repr="boom")
            bundle.add_screenshot(b"\x89PNG\r\n", name="login.png")
            bundle.add_dom("<html></html>")
            bundle.add_console([{"type": "log", "text": "hi"}])
            bundle.add_network([{"url": "/", "status": 200}])
            bundle.add_text("notes.txt", "context")
            target = bundle.write(Path(tmpdir) / "bundle.zip")
            extracted = extract_bundle(target)
            manifest = extracted["manifest"]
            self.assertEqual(manifest["test_name"], "login_test")
            self.assertEqual(manifest["error_repr"], "boom")
            names = {a["name"] for a in manifest["artifacts"]}
            self.assertIn("artifacts/login.png", names)
            self.assertIn("artifacts/dom.html", names)
            self.assertIn("artifacts/console.json", names)
            console_payload = json.loads(extracted["files"]["artifacts/console.json"])
            self.assertEqual(console_payload[0]["text"], "hi")

    def test_missing_trace_raises(self):
        bundle = FailureBundle(test_name="x", error_repr="err")
        with self.assertRaises(FailureBundleError):
            bundle.add_trace("does_not_exist.zip")

    def test_extract_missing_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.zip"
            import zipfile
            with zipfile.ZipFile(bad, "w") as zf:
                zf.writestr("noise.txt", "hi")
            with self.assertRaises(FailureBundleError):
                extract_bundle(bad)


if __name__ == "__main__":
    unittest.main()
