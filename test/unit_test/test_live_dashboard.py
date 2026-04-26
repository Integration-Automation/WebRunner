import json
import unittest
import urllib.request

from je_web_runner.utils.dashboard.live_dashboard import LiveDashboard
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestLiveDashboard(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True
        self._dashboard = LiveDashboard("127.0.0.1", 0)
        self._url = self._dashboard.start()

    def tearDown(self):
        self._dashboard.stop()
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_index_returns_html(self):
        # Local 127.0.0.1 dashboard, no schemes from user input — Bandit
        # B310 false positive on these test fixtures.
        with urllib.request.urlopen(self._url + "/", timeout=2) as response:  # nosec B310
            body = response.read().decode("utf-8")
        self.assertIn("<title>WebRunner live</title>", body)

    def test_records_endpoint_returns_payload(self):
        record_action_to_list("step_ok", None, None)
        record_action_to_list("step_fail", None, RuntimeError("boom"))
        with urllib.request.urlopen(self._url + "/records", timeout=2) as response:  # nosec B310
            payload = json.loads(response.read())
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["passed"], 1)
        self.assertEqual(payload["failed"], 1)
        names = [r["function_name"] for r in payload["records"]]
        self.assertEqual(names, ["step_ok", "step_fail"])

    def test_unknown_path_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url + "/nope", timeout=2)  # nosec B310
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
