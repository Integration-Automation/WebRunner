"""The redesigned aggregated dashboard: pages, assets and what the CSP allows."""
import json
import re
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from je_web_runner.utils.live_dashboard._charts import pass_rate_chart
from je_web_runner.utils.live_dashboard.server import DashboardConfig, DashboardServer


def _get(url: str) -> tuple[str, str]:
    with urllib.request.urlopen(url, timeout=5) as response:  # nosec B310 — localhost only
        return response.headers["Content-Type"], response.read().decode("utf-8")


def _seed(tmpdir: Path) -> DashboardConfig:
    ledger = tmpdir / "ledger.json"
    runs = [{"path": f"t{i % 3}.json", "passed": i % 4 != 0, "time": f"2026-09-{10 + i // 5:02d}T10:00:00"}
            for i in range(20)]
    ledger.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    quarantine = tmpdir / "q.json"
    quarantine.write_text(json.dumps({"entries": [
        {"test_id": "safe.json", "reason": "flaky", "flake_score": 0.7,
         "quarantined_at": "2026-09-20T01:02:03+00:00", "runs_when_added": 12,
         "triage_url": "https://tracker.example/T-1"},
        {"test_id": "evil.json", "reason": "x", "flake_score": 0.4,
         "quarantined_at": "2026-09-20T01:02:03+00:00", "triage_url": "javascript:alert(1)"},
    ]}), encoding="utf-8")
    locators = tmpdir / "locators.json"
    long_value = "//div" * 20
    locators.write_text(json.dumps({
        "total": 4, "weak": 1, "strong": 3, "average_score": 71.25, "threshold": 60,
        "weakest": [{"file_path": "a.json", "action_index": 2, "strategy": "XPATH", "value": long_value,
                     "score": 20, "reasons": ["deep selector"]}],
        "fallback_offenders": [{"file_path": "b.json", "name": "login_button", "value": "#login",
                                "hits": 10, "fallback_used": 4, "fallback_rate": 0.4}],
    }), encoding="utf-8")
    schedule = tmpdir / "schedule.json"
    schedule.write_text(json.dumps({"selected": ["fast.json"], "skipped": ["slow.json"], "total_seconds": 12.5,
                                    "total_cloud_slots": 2, "leftover_seconds": 3.0,
                                    "value_recovered": 0.81}), encoding="utf-8")
    triage = tmpdir / "triage.json"
    triage.write_text(json.dumps({"likely_cause": "Button renamed <b>", "category": "locator",
                                  "evidence": ["selector missing"], "next_steps": ["update locator"],
                                  "suggested_fix": "use data-testid", "confidence": 0.8,
                                  "test_name": "login.json", "error_signature": "NoSuchElement"}),
                      encoding="utf-8")
    return DashboardConfig(ledger_path=ledger, quarantine_path=quarantine, locator_findings_path=locators,
                           schedule_path=schedule, triage_report_path=triage)


class TestDashboardUi(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = DashboardServer(_seed(Path(cls.tmp.name)))
        cls.url = cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.tmp.cleanup()

    def page(self, path: str) -> str:
        return _get(self.url + path)[1]

    def test_every_page_has_the_shell_and_marks_its_nav_entry(self):
        for path in ("/", "/runs", "/flake", "/quarantine", "/locators", "/schedule", "/triage"):
            page = self.page(path)
            self.assertIn("<html lang='en'>", page, path)
            self.assertIn("name='viewport'", page, path)
            self.assertIn("<script src='/static/app.js' defer></script>", page, path)
            self.assertIn(f"<a href='{path}' aria-current='page'>", page, path)
            self.assertEqual(page.count("aria-current"), 1, path)

    def test_no_page_uses_inline_styles_or_scripts(self):
        # The CSP (default-src 'self') would block them.
        for path in ("/", "/runs", "/flake", "/quarantine", "/locators", "/schedule", "/triage", "/nope"):
            try:
                page = self.page(path)
            except urllib.error.HTTPError as error:  # the 404 page
                page = error.read().decode("utf-8")
            self.assertNotIn("style=", page, path)
            self.assertNotIn("<style", page, path)
            self.assertIsNone(re.search(r"<script(?![^>]*\bsrc=)", page), path)
            self.assertIsNone(re.search(r"<[^>]*\son[a-z]+\s*=", page), path)  # no onclick= etc.

    def test_assets_are_served_with_their_types(self):
        css_type, css = _get(self.url + "/static/app.css")
        js_type, js = _get(self.url + "/static/app.js")
        svg_type, svg = _get(self.url + "/static/favicon.svg")
        self.assertTrue(css_type.startswith("text/css"))
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertTrue(js_type.startswith("text/javascript"))
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        self.assertTrue(svg_type.startswith("image/svg+xml"))
        self.assertIn("<svg", svg)

    def test_overview_shows_status_cards_the_chart_and_latest_runs(self):
        page = self.page("/")
        self.assertIn("<div class='card bad'><div class='label'>Failed</div>", page)
        self.assertIn("class='chart'", page)
        self.assertIn("<h2>Latest runs</h2>", page)
        self.assertIn("href='/runs'>All runs</a>", page)

    def test_runs_page_limits_rows_and_offers_more(self):
        page = self.page("/runs?limit=5")
        self.assertIn("Showing 5 of 20 runs", page)
        self.assertEqual(page.count("<tr data-status="), 5)
        self.assertIn("href='/runs?limit=55'>Show more</a>", page)
        self.assertIn("data-status-filter='runs'", page)
        self.assertIn("<time datetime='2026-09-13T10:00:00'>", page)

    def test_flake_page_shows_pass_rate_and_a_score_meter(self):
        page = self.page("/flake")
        self.assertIn("<th class='num'>Pass rate</th>", page)
        self.assertIn("<meter", page)

    def test_quarantine_links_only_http_triage_urls(self):
        page = self.page("/quarantine")
        self.assertIn("<a href='https://tracker.example/T-1' rel='noopener noreferrer' target='_blank'>", page)
        self.assertNotIn("href='javascript:", page)
        self.assertIn("javascript:alert(1)", page)  # shown as text

    def test_locators_page_keeps_the_full_value_and_lists_offenders(self):
        page = self.page("/locators")
        self.assertIn("title='" + "//div" * 20 + "'", page)
        self.assertIn("login_button", page)
        self.assertIn("<div class='label'>Threshold</div><div class='value'>60</div>", page)

    def test_schedule_page(self):
        page = self.page("/schedule")
        self.assertIn("fast.json", page)
        self.assertIn("slow.json", page)
        self.assertIn("<div class='label'>Value recovered</div><div class='value'>0.81</div>", page)

    def test_triage_page_escapes_the_report(self):
        page = self.page("/triage")
        self.assertIn("Button renamed &lt;b&gt;", page)
        self.assertIn("<ol><li>update locator</li></ol>", page)

    def test_trend_api(self):
        _type, body = _get(self.url + "/api/trend")
        trend = json.loads(body)
        self.assertEqual(trend["totals"]["total"], 20)
        self.assertEqual(len(trend["daily"]), 4)


class TestEmptyDashboard(unittest.TestCase):

    def test_new_pages_explain_how_to_get_data(self):
        with DashboardServer() as server:
            self.assertIn("schedule_path", _get(server.url + "/schedule")[1])
            self.assertIn("triage_report_path", _get(server.url + "/triage")[1])
            overview = _get(server.url + "/")[1]
        self.assertIn("No dated runs to chart yet.", overview)
        self.assertNotIn("class='card bad'", overview)


class TestChart(unittest.TestCase):

    def test_single_day_and_unknown_dates(self):
        daily = [{"label": "unknown", "passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
                 {"label": "2026-09-01", "passed": 3, "failed": 1, "total": 4, "pass_rate": 0.75}]
        svg = pass_rate_chart(daily)
        self.assertEqual(svg.count("<circle"), 1)
        self.assertIn("75.0% passed (3/4), 1 failed", svg)
        self.assertEqual(pass_rate_chart([]), "")


if __name__ == "__main__":
    unittest.main()
