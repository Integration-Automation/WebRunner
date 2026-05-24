"""Unit tests for je_web_runner.utils.time_freezer."""
import unittest
from datetime import datetime, timezone

from je_web_runner.utils.time_freezer.freezer import (
    FreezeConfig,
    TimeFreezerError,
    attach_to_cdp,
    build_freezer_script,
    freeze_at,
    slow_motion,
    to_epoch_ms,
)


class TestToEpochMs(unittest.TestCase):

    def test_iso_string(self):
        self.assertEqual(
            to_epoch_ms("2026-01-01T00:00:00Z"),
            int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000),
        )

    def test_iso_with_offset(self):
        ms = to_epoch_ms("2026-01-01T08:00:00+08:00")
        self.assertEqual(ms, int(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000))

    def test_naive_datetime_treated_as_utc(self):
        ms = to_epoch_ms(datetime(2026, 1, 1))
        self.assertEqual(ms, int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000))

    def test_int_seconds(self):
        # Anything below 1e12 is treated as seconds, then × 1000
        self.assertEqual(to_epoch_ms(1735689600), 1735689600000)

    def test_int_milliseconds(self):
        self.assertEqual(to_epoch_ms(1735689600000), 1735689600000)

    def test_bool_rejected(self):
        with self.assertRaises(TimeFreezerError):
            to_epoch_ms(True)

    def test_bad_string(self):
        with self.assertRaises(TimeFreezerError):
            to_epoch_ms("not a time")

    def test_unsupported_type(self):
        with self.assertRaises(TimeFreezerError):
            to_epoch_ms([])  # type: ignore[arg-type]


class TestFreezeConfig(unittest.TestCase):

    def test_default(self):
        cfg = FreezeConfig(epoch_ms=1)
        self.assertEqual(cfg.advance_ms_per_real_second, 0.0)

    def test_negative_epoch_rejected(self):
        with self.assertRaises(TimeFreezerError):
            FreezeConfig(epoch_ms=-1)

    def test_negative_slope_rejected(self):
        with self.assertRaises(TimeFreezerError):
            FreezeConfig(epoch_ms=0, advance_ms_per_real_second=-1.0)


class TestBuildScript(unittest.TestCase):

    def test_embeds_epoch(self):
        cfg = FreezeConfig(epoch_ms=123_456_789)
        script = build_freezer_script(cfg)
        self.assertIn("123456789", script)
        self.assertIn("FakeDate", script)

    def test_disable_date_patch(self):
        cfg = FreezeConfig(epoch_ms=1, patch_date_constructor=False)
        script = build_freezer_script(cfg)
        self.assertIn("Date.now = virtualNow", script)

    def test_disable_performance_patch(self):
        cfg = FreezeConfig(epoch_ms=1, patch_performance_now=False)
        script = build_freezer_script(cfg)
        self.assertIn("__PATCH_PERF__ = false", script)

    def test_rejects_non_config(self):
        with self.assertRaises(TimeFreezerError):
            build_freezer_script("string")  # type: ignore[arg-type]


class TestAttach(unittest.TestCase):

    def test_calls_attach_with_script(self):
        seen: list = []
        result = attach_to_cdp(seen.append, FreezeConfig(epoch_ms=42))
        self.assertIn("42", seen[0])
        self.assertIsNone(result)

    def test_wraps_attach_failure(self):
        def boom(_script):
            raise RuntimeError("no cdp")
        with self.assertRaises(TimeFreezerError):
            attach_to_cdp(boom, FreezeConfig(epoch_ms=1))


class TestConvenience(unittest.TestCase):

    def test_freeze_at_from_iso(self):
        cfg = freeze_at("2026-05-24T12:00:00Z")
        self.assertEqual(cfg.advance_ms_per_real_second, 0.0)

    def test_slow_motion(self):
        cfg = slow_motion("2026-01-01T00:00:00Z", real_seconds_per_virtual_second=10)
        self.assertEqual(cfg.advance_ms_per_real_second, 100.0)  # 1000ms/10s

    def test_slow_motion_validates(self):
        with self.assertRaises(TimeFreezerError):
            slow_motion("2026-01-01T00:00:00Z", real_seconds_per_virtual_second=0)
        with self.assertRaises(TimeFreezerError):
            slow_motion("2026-01-01T00:00:00Z", real_seconds_per_virtual_second=-1)


if __name__ == "__main__":
    unittest.main()
