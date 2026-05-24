"""Unit tests for je_web_runner.utils.locator_health."""
import json
import tempfile
import threading
import unittest
from pathlib import Path

from je_web_runner.utils.locator_health.health_report import (
    FallbackHitTracker,
    LocatorFinding,
    LocatorHealthError,
    LocatorHealthReport,
    UpgradeSuggestion,
    apply_upgrades,
    build_health_report,
    fallback_hit_tracker,
    render_health_markdown,
    save_health_report,
    scan_action_file,
    scan_project,
    suggest_upgrade,
    suggest_upgrades,
)


def _write_action_file(path: Path, actions):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(actions, fp)


class TestFallbackHitTracker(unittest.TestCase):

    def test_counts_primary_and_fallback(self):
        tracker = FallbackHitTracker()
        tracker.track_primary("login_btn")
        tracker.track_primary("login_btn")
        tracker.track_fallback("login_btn")
        stats = tracker.stats()
        self.assertEqual(stats["login_btn"]["hits"], 3)
        self.assertEqual(stats["login_btn"]["fallback_used"], 1)

    def test_thread_safe(self):
        tracker = FallbackHitTracker()
        N = 200

        def hammer():
            for _ in range(N):
                tracker.track_primary("x")
                tracker.track_fallback("x")

        threads = [threading.Thread(target=hammer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stats = tracker.stats()
        self.assertEqual(stats["x"]["hits"], 4 * N * 2)
        self.assertEqual(stats["x"]["fallback_used"], 4 * N)

    def test_clear_resets(self):
        tracker = FallbackHitTracker()
        tracker.track_primary("a")
        tracker.clear()
        self.assertEqual(tracker.stats(), {})


class TestScanActionFile(unittest.TestCase):

    def test_missing_file_raises(self):
        with self.assertRaises(LocatorHealthError):
            scan_action_file("/nope/missing.json")

    def test_malformed_json_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(LocatorHealthError):
                scan_action_file(path)

    def test_scores_each_locator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.json"
            _write_action_file(path, [
                ["WR_save_test_object", {"object_type": "ID", "test_object_name": "login_btn"}],
                ["WR_save_test_object", {"object_type": "XPATH", "test_object_name": "//div/div/div/div/div/span"}],
                ["WR_to_url", {"url": "https://x"}],
            ])
            findings = scan_action_file(path)
            self.assertEqual(len(findings), 2)
            ids = {(f.strategy, f.score) for f in findings}
            id_score = next(f for f in findings if f.strategy == "ID").score
            xpath_score = next(f for f in findings if f.strategy == "XPATH").score
            self.assertGreater(id_score, xpath_score)


class TestScanProject(unittest.TestCase):

    def test_walks_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_action_file(root / "a.json", [
                ["WR_save", {"object_type": "ID", "test_object_name": "x"}],
            ])
            _write_action_file(root / "sub" / "b.json", [
                ["WR_save", {"object_type": "XPATH", "test_object_name": "//a"}],
            ])
            (root / "notes.txt").write_text("hi", encoding="utf-8")
            findings = scan_project(root)
            self.assertEqual(len(findings), 2)

    def test_missing_root_raises(self):
        with self.assertRaises(LocatorHealthError):
            scan_project("/no/such/dir")

    def test_skips_unparseable_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "broken.json").write_text("{{{", encoding="utf-8")
            _write_action_file(root / "ok.json", [
                ["WR_save", {"object_type": "ID", "test_object_name": "x"}],
            ])
            findings = scan_project(root)
            self.assertEqual(len(findings), 1)


class TestBuildHealthReport(unittest.TestCase):

    def _findings(self, *triples):
        return [
            LocatorFinding(
                file_path="x.json", action_index=i,
                strategy=s, value=v, score=score,
            )
            for i, (s, v, score) in enumerate(triples)
        ]

    def test_empty_returns_zeros(self):
        report = build_health_report([])
        self.assertEqual(report.total, 0)
        self.assertEqual(report.average_score, 0.0)

    def test_aggregates_correctly(self):
        report = build_health_report(self._findings(
            ("ID", "ok", 90),
            ("XPATH", "//a", 30),
            ("CSS_SELECTOR", ".btn", 70),
        ), threshold=60)
        self.assertEqual(report.total, 3)
        self.assertEqual(report.weak, 1)
        self.assertEqual(report.strong, 2)
        self.assertAlmostEqual(report.average_score, (90 + 30 + 70) / 3, places=2)
        self.assertEqual(report.weakest[0].score, 30)

    def test_fallback_offenders_sorted_by_rate(self):
        findings = [
            LocatorFinding(
                file_path="x.json", action_index=0, strategy="ID", value="a",
                score=80, hits=10, fallback_used=5,
            ),
            LocatorFinding(
                file_path="x.json", action_index=1, strategy="ID", value="b",
                score=80, hits=10, fallback_used=8,
            ),
            LocatorFinding(
                file_path="x.json", action_index=2, strategy="ID", value="c",
                score=80, hits=10, fallback_used=1,  # below threshold
            ),
        ]
        report = build_health_report(findings, fallback_min_rate=0.4)
        self.assertEqual(len(report.fallback_offenders), 2)
        self.assertEqual(report.fallback_offenders[0].value, "b")


class TestSuggestUpgrade(unittest.TestCase):

    def test_xpath_with_id_attr_suggests_id(self):
        finding = LocatorFinding(
            file_path="x.json", action_index=0,
            strategy="XPATH", value="//div[@id='login']", score=40,
        )
        sug = suggest_upgrade(finding)
        self.assertIsNotNone(sug)
        self.assertEqual(sug.to_strategy, "ID")
        self.assertEqual(sug.to_value, "login")

    def test_xpath_with_testid_suggests_css(self):
        finding = LocatorFinding(
            file_path="x.json", action_index=0,
            strategy="XPATH", value="//button[@data-testid='go']", score=40,
        )
        sug = suggest_upgrade(finding)
        self.assertIsNotNone(sug)
        self.assertEqual(sug.to_strategy, "CSS_SELECTOR")
        self.assertEqual(sug.to_value, "[data-testid='go']")

    def test_css_single_id_suggests_id(self):
        finding = LocatorFinding(
            file_path="x.json", action_index=0,
            strategy="CSS_SELECTOR", value="#login-btn", score=70,
        )
        sug = suggest_upgrade(finding)
        self.assertEqual(sug.to_strategy, "ID")
        self.assertEqual(sug.to_value, "login-btn")

    def test_id_no_suggestion(self):
        finding = LocatorFinding(
            file_path="x.json", action_index=0,
            strategy="ID", value="ok", score=90,
        )
        self.assertIsNone(suggest_upgrade(finding))


class TestSuggestUpgrades(unittest.TestCase):

    def test_filters_below_threshold(self):
        findings = [
            LocatorFinding(file_path="x", action_index=0, strategy="XPATH",
                           value="//div[@id='a']", score=40),
            LocatorFinding(file_path="x", action_index=1, strategy="XPATH",
                           value="//div[@id='b']", score=80),
        ]
        sugs = suggest_upgrades(findings, only_below=50)
        self.assertEqual(len(sugs), 1)


class TestApplyUpgrades(unittest.TestCase):

    def test_rewrites_in_place_safely(self):
        actions = [
            ["WR_save", {"object_type": "XPATH", "test_object_name": "//div[@id='x']"}],
            ["WR_click", {"object_type": "ID", "test_object_name": "x"}],
        ]
        sugs = [UpgradeSuggestion(
            file_path="x", action_index=0,
            from_strategy="XPATH", from_value="//div[@id='x']",
            to_strategy="ID", to_value="x",
            rationale="r",
        )]
        new_actions = apply_upgrades(actions, sugs)
        self.assertEqual(new_actions[0][1]["object_type"], "ID")
        self.assertEqual(new_actions[0][1]["test_object_name"], "x")
        # Original is untouched.
        self.assertEqual(actions[0][1]["object_type"], "XPATH")
        # Second action unaffected.
        self.assertEqual(new_actions[1][1]["object_type"], "ID")

    def test_out_of_range_index_is_ignored(self):
        actions = [["WR_save", {"object_type": "ID", "test_object_name": "x"}]]
        sugs = [UpgradeSuggestion(
            file_path="x", action_index=99,
            from_strategy="X", from_value="x",
            to_strategy="Y", to_value="y", rationale="r",
        )]
        new_actions = apply_upgrades(actions, sugs)
        self.assertEqual(new_actions, actions)


class TestRendering(unittest.TestCase):

    def test_markdown_contains_required_sections(self):
        findings = [
            LocatorFinding(file_path="a.json", action_index=0,
                           strategy="XPATH", value="//x", score=30,
                           reasons=["deep"]),
        ]
        report = build_health_report(findings, threshold=60)
        md = render_health_markdown(report)
        self.assertIn("Locator health report", md)
        self.assertIn("Weakest locators", md)
        self.assertIn("`XPATH`", md)

    def test_save_round_trips(self):
        report = build_health_report([
            LocatorFinding(file_path="a.json", action_index=0,
                           strategy="ID", value="x", score=90),
        ])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_health_report(report, Path(tmpdir) / "r.json")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["total"], 1)
            self.assertEqual(data["strong"], 1)


class TestModuleSingleton(unittest.TestCase):

    def test_module_level_tracker_isolated_between_tests(self):
        fallback_hit_tracker.clear()
        fallback_hit_tracker.track_primary("foo")
        self.assertEqual(fallback_hit_tracker.stats()["foo"]["hits"], 1)
        fallback_hit_tracker.clear()


if __name__ == "__main__":
    unittest.main()
