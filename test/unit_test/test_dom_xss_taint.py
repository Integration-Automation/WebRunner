"""Unit tests for je_web_runner.utils.dom_xss_taint."""
import unittest

from je_web_runner.utils.dom_xss_taint.taint import (
    DomXssTaintError,
    INSTALL_SCRIPT,
    TaintFinding,
    assert_no_taint,
    assert_only_safe_sinks,
    make_canaries,
    parse_findings,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("__wr_taint__", INSTALL_SCRIPT)
        self.assertIn("innerHTML", INSTALL_SCRIPT)


class TestCanaries(unittest.TestCase):

    def test_basic(self):
        c = make_canaries("login")
        self.assertEqual(len(c), 2)
        self.assertTrue(all(s.startswith("WRXSS-login-") for s in c))

    def test_empty(self):
        with self.assertRaises(DomXssTaintError):
            make_canaries("")


class TestParse(unittest.TestCase):

    def test_basic(self):
        out = parse_findings([{"sink": "innerHTML", "canary": "X"}])
        self.assertEqual(out[0].sink, "innerHTML")

    def test_skip_missing(self):
        out = parse_findings([{"sink": "innerHTML"}])
        self.assertEqual(out, [])

    def test_skip_non_dict(self):
        self.assertEqual(parse_findings(["x"]), [])

    def test_bad(self):
        with self.assertRaises(DomXssTaintError):
            parse_findings("nope")


class TestAssertNoTaint(unittest.TestCase):

    def test_pass(self):
        assert_no_taint([])

    def test_fail(self):
        with self.assertRaises(DomXssTaintError):
            assert_no_taint([TaintFinding(sink="innerHTML", canary="X")])


class TestOnlySafeSinks(unittest.TestCase):

    def test_pass(self):
        assert_only_safe_sinks(
            [TaintFinding(sink="innerHTML", canary="X")],
            allowed_sinks=["innerHTML"],
        )

    def test_fail(self):
        with self.assertRaises(DomXssTaintError):
            assert_only_safe_sinks(
                [TaintFinding(sink="eval", canary="X")],
                allowed_sinks=["innerHTML"],
            )


if __name__ == "__main__":
    unittest.main()
