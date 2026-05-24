"""Unit tests for je_web_runner.utils.live_dashboard.server (aggregator UI)."""
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from je_web_runner.utils.flake_detector.detector import (
    QuarantineEntry,
    QuarantineRegistry,
)
from je_web_runner.utils.live_dashboard.server import (
    DashboardConfig,
    DashboardServer,
    LiveDashboardError,
    build_summary,
)


def _iso(dt):
    return dt.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def _write_ledger(path: Path, runs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"runs": runs}), encoding="utf-8")


def _make_seeded_config(tmpdir: Path) -> DashboardConfig:
    ledger = tmpdir / "ledger.json"
    now = datetime.now(timezone.utc)
    _write_ledger(ledger, [
        {"path": "a.json", "passed": True,  "time": _iso(now)},
        {"path": "a.json", "passed": False, "time": _iso(now)},
        {"path": "a.json", "passed": True,  "time": _iso(now)},
        {"path": "a.json", "passed": False, "time": _iso(now)},
        {"path": "b.json", "passed": True,  "time": _iso(now)},
    ])
    quarantine = tmpdir / "quarantine.json"
    reg = QuarantineRegistry(quarantine)
    reg.add(QuarantineEntry(
        test_id="a.json", reason="auto", flake_score=0.6,
        quarantined_at=_iso(now),
    ))
    locator = tmpdir / "locator.json"
    locator.write_text(json.dumps({
        "total": 10, "weak": 3, "strong": 7,
        "average_score": 75.5, "threshold": 60,
        "weakest": [
            {"file_path": "actions/login.json", "action_index": 1,
             "strategy": "XPATH", "value": "//div/div/span",
             "score": 30, "reasons": ["deep selector"]},
        ],
    }), encoding="utf-8")
    return DashboardConfig(
        ledger_path=ledger,
        quarantine_path=quarantine,
        locator_findings_path=locator,
    )


class TestBuildSummary(unittest.TestCase):

    def test_aggregates_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_seeded_config(Path(tmpdir))
            summary = build_summary(config)
            self.assertEqual(summary["total_runs"], 5)
            self.assertEqual(summary["passed"], 3)
            self.assertEqual(summary["failed"], 2)
            self.assertAlmostEqual(summary["pass_rate"], 0.6, places=2)
            self.assertEqual(summary["quarantined_tests"], 1)
            self.assertEqual(summary["weak_locators"], 3)

    def test_empty_config_is_safe(self):
        summary = build_summary(DashboardConfig())
        self.assertEqual(summary["total_runs"], 0)
        self.assertEqual(summary["pass_rate"], 0.0)
        self.assertEqual(summary["weak_locators"], 0)

    def test_missing_files_skipped(self):
        config = DashboardConfig(
            ledger_path=Path("/no/such/ledger.json"),
            quarantine_path=Path("/no/such/q.json"),
            locator_findings_path=Path("/no/such/l.json"),
        )
        summary = build_summary(config)
        self.assertEqual(summary["total_runs"], 0)


class TestServerLifecycle(unittest.TestCase):

    def test_url_before_start_raises(self):
        with self.assertRaises(LiveDashboardError):
            _ = DashboardServer().url

    def test_start_stop(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = _make_seeded_config(Path(tmpdir))
            server = DashboardServer(config)
            url = server.start()
            self.assertTrue(url.startswith("http://127.0.0.1:"))
            server.stop()

    def test_double_start_raises(self):
        server = DashboardServer()
        server.start()
        try:
            with self.assertRaises(LiveDashboardError):
                server.start()
        finally:
            server.stop()

    def test_context_manager(self):
        with DashboardServer() as server:
            self.assertTrue(server.url.startswith("http://"))

    def test_stop_when_not_started_is_noop(self):
        DashboardServer().stop()


def _http_get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=5) as resp:  # nosec B310 — localhost only
        return resp.read()


def _http_get_json(url: str):
    return json.loads(_http_get(url).decode("utf-8"))


class TestHttpEndpoints(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = _make_seeded_config(Path(self.tmp.name))
        self.server = DashboardServer(self.config)
        self.server.start()
        self.addCleanup(self.server.stop)

    def test_overview_returns_html(self):
        body = _http_get(self.server.url + "/").decode("utf-8")
        self.assertIn("<!DOCTYPE html>", body)
        self.assertIn("WebRunner overview", body)
        self.assertIn("Total runs", body)

    def test_runs_page_lists_recent(self):
        body = _http_get(self.server.url + "/runs").decode("utf-8")
        self.assertIn("a.json", body)
        self.assertIn("FAIL", body)
        self.assertIn("PASS", body)

    def test_flake_page_lists_flaky_tests(self):
        body = _http_get(self.server.url + "/flake").decode("utf-8")
        self.assertIn("a.json", body)

    def test_quarantine_page_shows_entries(self):
        body = _http_get(self.server.url + "/quarantine").decode("utf-8")
        self.assertIn("a.json", body)

    def test_locators_page_shows_weakest(self):
        body = _http_get(self.server.url + "/locators").decode("utf-8")
        self.assertIn("XPATH", body)
        self.assertIn("deep selector", body)

    def test_unknown_route_returns_404(self):
        url = self.server.url + "/no-such-route"
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _http_get(url)
        self.assertEqual(cm.exception.code, 404)

    def test_api_summary_returns_json(self):
        payload = _http_get_json(self.server.url + "/api/summary")
        self.assertEqual(payload["total_runs"], 5)
        self.assertEqual(payload["quarantined_tests"], 1)

    def test_api_runs_respects_limit(self):
        payload = _http_get_json(self.server.url + "/api/runs?limit=2")
        self.assertLessEqual(len(payload), 2)

    def test_api_runs_bad_limit_falls_back(self):
        payload = _http_get_json(self.server.url + "/api/runs?limit=junk")
        self.assertGreater(len(payload), 0)

    def test_api_flake_payload_shape(self):
        payload = _http_get_json(self.server.url + "/api/flake")
        self.assertTrue(any(e["path"] == "a.json" for e in payload))

    def test_api_quarantine_payload(self):
        payload = _http_get_json(self.server.url + "/api/quarantine")
        self.assertEqual(payload[0]["test_id"], "a.json")

    def test_api_locators_payload(self):
        payload = _http_get_json(self.server.url + "/api/locators")
        self.assertEqual(payload["total"], 10)

    def test_healthz(self):
        body = _http_get(self.server.url + "/healthz")
        self.assertEqual(body, b"ok")


class TestEmptyServer(unittest.TestCase):

    def test_endpoints_work_with_no_data(self):
        with DashboardServer() as server:
            overview = _http_get(server.url + "/").decode("utf-8")
            self.assertIn("WebRunner overview", overview)
            empty_runs = _http_get(server.url + "/runs").decode("utf-8")
            self.assertIn("No runs", empty_runs)
            empty_flake = _http_get(server.url + "/flake").decode("utf-8")
            self.assertIn("No flaky", empty_flake)
            empty_q = _http_get(server.url + "/quarantine").decode("utf-8")
            self.assertIn("empty", empty_q.lower())
            empty_l = _http_get(server.url + "/locators").decode("utf-8")
            self.assertIn("No locator", empty_l)


if __name__ == "__main__":
    unittest.main()
