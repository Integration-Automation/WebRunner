"""Unit tests for je_web_runner.utils.compute_pressure."""
import unittest

from je_web_runner.utils.compute_pressure.pressure import (
    ComputePressureError,
    INSTALL_SCRIPT,
    PressureLevel,
    PressureLog,
    PressureReaction,
    assert_observer_disconnected,
    assert_reaction_to,
    assert_throttled_at_or_above,
    parse_log,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("PressureObserver", INSTALL_SCRIPT)
        self.assertIn("__wr_cp__", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log({
            "reactions": [{"name": "throttle", "level": "serious"}],
            "fires": ["serious"], "disconnectCount": 1,
        })
        self.assertEqual(log.reactions[0].level, PressureLevel.SERIOUS)
        self.assertEqual(log.disconnect_count, 1)

    def test_bad(self):
        with self.assertRaises(ComputePressureError):
            parse_log("nope")

    def test_bad_level(self):
        with self.assertRaises(ComputePressureError):
            parse_log({"reactions": [{"level": "weird"}]})

    def test_bad_fire(self):
        with self.assertRaises(ComputePressureError):
            parse_log({"fires": ["weird"]})


class TestReaction(unittest.TestCase):

    def test_pass(self):
        r = assert_reaction_to(
            PressureLog(reactions=[PressureReaction(name="x",
                                                    level=PressureLevel.CRITICAL)]),
            level=PressureLevel.SERIOUS,
        )
        self.assertEqual(r.name, "x")

    def test_named(self):
        with self.assertRaises(ComputePressureError):
            assert_reaction_to(
                PressureLog(reactions=[PressureReaction(name="other",
                                                        level=PressureLevel.CRITICAL)]),
                level=PressureLevel.SERIOUS, name="expected",
            )

    def test_fail(self):
        with self.assertRaises(ComputePressureError):
            assert_reaction_to(
                PressureLog(reactions=[PressureReaction(name="x",
                                                        level=PressureLevel.FAIR)]),
                level=PressureLevel.CRITICAL,
            )

    def test_bad_level(self):
        with self.assertRaises(ComputePressureError):
            assert_reaction_to(PressureLog(), level="critical")


class TestThrottled(unittest.TestCase):

    def test_pass(self):
        assert_throttled_at_or_above(
            PressureLog(reactions=[PressureReaction(name="x",
                                                    level=PressureLevel.CRITICAL)],
                        fires=[PressureLevel.SERIOUS]),
            level=PressureLevel.SERIOUS,
        )

    def test_skip_low_fires(self):
        # harness never fired SERIOUS+, so nothing to verify
        assert_throttled_at_or_above(
            PressureLog(fires=[PressureLevel.NOMINAL]),
            level=PressureLevel.SERIOUS,
        )

    def test_fail(self):
        with self.assertRaises(ComputePressureError):
            assert_throttled_at_or_above(
                PressureLog(fires=[PressureLevel.CRITICAL],
                            reactions=[PressureReaction(name="x",
                                                        level=PressureLevel.FAIR)]),
                level=PressureLevel.SERIOUS,
            )


class TestDisconnect(unittest.TestCase):

    def test_pass(self):
        assert_observer_disconnected(PressureLog(disconnect_count=1))

    def test_fail(self):
        with self.assertRaises(ComputePressureError):
            assert_observer_disconnected(PressureLog())


if __name__ == "__main__":
    unittest.main()
