"""Unit tests for je_web_runner.utils.forced_colors_mode."""
import unittest

from je_web_runner.utils.forced_colors_mode.modes import (
    DEFAULT_PROFILES,
    ColorScheme,
    ForcedColorsModeError,
    MediaProfile,
    ModeAuditReport,
    StyleSnapshot,
    apply_profile,
    assert_no_invisible,
    audit_modes,
    diff_snapshot,
)


class TestProfile(unittest.TestCase):

    def test_to_cdp_features_default(self):
        features = MediaProfile(name="baseline").to_cdp_features()
        names = {f["name"] for f in features}
        self.assertEqual(names, {
            "prefers-color-scheme", "prefers-reduced-motion",
            "forced-colors", "prefers-contrast",
        })

    def test_dark_profile(self):
        features = MediaProfile(
            name="d", color_scheme=ColorScheme.DARK,
        ).to_cdp_features()
        dark = next(f for f in features if f["name"] == "prefers-color-scheme")
        self.assertEqual(dark["value"], "dark")

    def test_default_profiles_count(self):
        self.assertEqual(len(DEFAULT_PROFILES), 5)
        names = {p.name for p in DEFAULT_PROFILES}
        self.assertIn("dark", names)
        self.assertIn("high-contrast", names)


class TestApplyProfile(unittest.TestCase):

    def test_passes_features_to_callable(self):
        seen: list = []
        apply_profile(MediaProfile(name="x"), seen.append)
        self.assertEqual(len(seen[0]), 4)

    def test_wraps_cdp_failure(self):
        def boom(_):
            raise RuntimeError("no cdp")
        with self.assertRaises(ForcedColorsModeError):
            apply_profile(MediaProfile(name="x"), boom)

    def test_rejects_non_profile(self):
        with self.assertRaises(ForcedColorsModeError):
            apply_profile("not a profile", lambda f: None)  # type: ignore[arg-type]


class TestStyleSnapshot(unittest.TestCase):

    def test_invisible_when_same_colour(self):
        self.assertTrue(StyleSnapshot(
            background_color="#fff", color="#FFF",
        ).is_invisible())

    def test_visible_otherwise(self):
        self.assertFalse(StyleSnapshot(
            background_color="#fff", color="#000",
        ).is_invisible())

    def test_no_background_means_visible(self):
        self.assertFalse(StyleSnapshot(
            background_color="", color="",
        ).is_invisible())


class TestDiffSnapshot(unittest.TestCase):

    def test_identical_returns_none(self):
        snap = StyleSnapshot(background_color="#000", color="#fff")
        self.assertIsNone(diff_snapshot("#x", "a", "b", snap, snap))

    def test_field_diff(self):
        a = StyleSnapshot(background_color="#000", color="#fff")
        b = StyleSnapshot(background_color="#fff", color="#000")
        diff = diff_snapshot("#x", "a", "b", a, b)
        self.assertIsNotNone(diff)
        self.assertIn("background_color", diff.changed_fields)

    def test_became_invisible_flag(self):
        baseline = StyleSnapshot(background_color="#000", color="#fff")
        bad = StyleSnapshot(background_color="#fff", color="#fff")
        diff = diff_snapshot("#x", "a", "b", baseline, bad)
        self.assertTrue(diff.became_invisible)

    def test_rejects_non_snapshot(self):
        with self.assertRaises(ForcedColorsModeError):
            diff_snapshot("#x", "a", "b", "not", "snap")  # type: ignore[arg-type]


class TestAuditModes(unittest.TestCase):

    def test_missing_baseline_raises(self):
        with self.assertRaises(ForcedColorsModeError):
            audit_modes("baseline", {"dark": {}})

    def test_clean_run(self):
        snap = StyleSnapshot(background_color="#fff", color="#000")
        snapshots = {
            "baseline": {"#a": snap},
            "dark": {"#a": snap},
        }
        report = audit_modes("baseline", snapshots)
        self.assertTrue(report.passed())
        self.assertEqual(report.diffs, [])

    def test_records_field_changes_without_invisibility(self):
        baseline = StyleSnapshot(background_color="#fff", color="#000")
        dark = StyleSnapshot(background_color="#000", color="#fff")
        report = audit_modes("baseline", {
            "baseline": {"#a": baseline},
            "dark": {"#a": dark},
        })
        self.assertEqual(len(report.diffs), 1)
        self.assertTrue(report.passed())  # invisible-free

    def test_flags_invisible(self):
        baseline = StyleSnapshot(background_color="#fff", color="#000")
        broken = StyleSnapshot(background_color="#fff", color="#fff")
        report = audit_modes("baseline", {
            "baseline": {"#a": baseline},
            "high-contrast": {"#a": broken},
        })
        self.assertFalse(report.passed())
        self.assertIn("high-contrast", report.invisible_in_modes)

    def test_skips_unknown_selectors(self):
        baseline = StyleSnapshot(background_color="#fff", color="#000")
        report = audit_modes("baseline", {
            "baseline": {"#a": baseline},
            "dark": {"#b": baseline},
        })
        self.assertEqual(report.diffs, [])


class TestAssertNoInvisible(unittest.TestCase):

    def test_pass(self):
        assert_no_invisible(ModeAuditReport())

    def test_fail(self):
        report = ModeAuditReport(invisible_in_modes={"dark": ["#a", "#b"]})
        with self.assertRaises(ForcedColorsModeError):
            assert_no_invisible(report)

    def test_rejects_non_report(self):
        with self.assertRaises(ForcedColorsModeError):
            assert_no_invisible("not a report")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
