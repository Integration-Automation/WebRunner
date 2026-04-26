"""
Integration: live_dashboard + test_record + visual_review.

Real-HTTP exercise of the dashboard endpoints and the visual-diff review
UI's accept-baseline workflow.
"""
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from je_web_runner.utils.dashboard.live_dashboard import LiveDashboard
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)
from je_web_runner.utils.visual_review.review_server import VisualReviewServer


class TestLiveDashboardRoundTrip(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original_init = test_record_instance.init_record
        test_record_instance.init_record = True
        self.dashboard = LiveDashboard("127.0.0.1", 0)
        self.url = self.dashboard.start()

    def tearDown(self):
        self.dashboard.stop()
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original_init

    def test_records_endpoint_reflects_added_records(self):
        record_action_to_list("step_pass", None, None)
        record_action_to_list("step_fail", None, RuntimeError("bad"))
        with urllib.request.urlopen(self.url + "/records", timeout=2) as response:  # nosec B310 — local fixture
            payload = json.loads(response.read())
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["passed"], 1)
        self.assertEqual(payload["failed"], 1)
        names = [record["function_name"] for record in payload["records"]]
        self.assertEqual(names, ["step_pass", "step_fail"])


class TestVisualReviewAcceptBaseline(unittest.TestCase):

    def test_accept_replaces_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            current_dir = Path(tmpdir) / "current"
            baseline_dir.mkdir()
            current_dir.mkdir()
            (baseline_dir / "home.png").write_bytes(b"old")
            (current_dir / "home.png").write_bytes(b"new")

            server = VisualReviewServer(str(baseline_dir), str(current_dir))
            url = server.start()
            try:
                # The index lists the diff
                with urllib.request.urlopen(url + "/", timeout=2) as response:  # nosec B310
                    page = response.read().decode("utf-8")
                self.assertIn("home.png", page)
                # Accept the current image as baseline
                payload = urllib.parse.urlencode({"name": "home.png"}).encode("utf-8")
                request = urllib.request.Request(url + "/accept", data=payload, method="POST")
                request.add_header("Content-Type", "application/x-www-form-urlencoded")
                opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
                with opener.open(request, timeout=2):  # nosec B310
                    pass
                # Baseline now equals the current bytes
                self.assertEqual(
                    (baseline_dir / "home.png").read_bytes(),
                    b"new",
                )
                self.assertEqual(server.accepted, ["home.png"])
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
