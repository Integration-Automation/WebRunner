"""Unit tests for je_web_runner.utils.speculation_rules."""
import unittest

from je_web_runner.utils.speculation_rules.rules import (
    HARVEST_LOG_SCRIPT,
    INSTALL_LISTENER_SCRIPT,
    PrerenderLog,
    SpeculationRule,
    SpeculationRulesError,
    assert_activated,
    assert_fire_count,
    assert_no_double_fire,
    build_script_tag,
    parse_log,
)


class TestSpeculationRule(unittest.TestCase):

    def test_list_needs_urls(self):
        with self.assertRaises(SpeculationRulesError):
            SpeculationRule(source="list")

    def test_unknown_source(self):
        with self.assertRaises(SpeculationRulesError):
            SpeculationRule(source="weird", urls=["/a"])

    def test_bad_eagerness(self):
        with self.assertRaises(SpeculationRulesError):
            SpeculationRule(source="list", urls=["/a"], eagerness="urgent")


class TestBuildScript(unittest.TestCase):

    def test_renders_prerender(self):
        tag = build_script_tag(
            prerender=[SpeculationRule(source="list", urls=["/a", "/b"])],
        )
        self.assertTrue(tag.startswith('<script type="speculationrules">'))
        self.assertIn('"prerender"', tag)
        self.assertIn("/a", tag)
        self.assertIn("/b", tag)

    def test_renders_prefetch_only(self):
        tag = build_script_tag(prefetch=[SpeculationRule(source="list", urls=["/x"])])
        self.assertIn('"prefetch"', tag)
        self.assertNotIn('"prerender"', tag)

    def test_document_source(self):
        tag = build_script_tag(prerender=[SpeculationRule(
            source="document", where={"href_matches": "/news/*"},
        )])
        self.assertIn('"where"', tag)

    def test_empty_raises(self):
        with self.assertRaises(SpeculationRulesError):
            build_script_tag()


class TestScripts(unittest.TestCase):

    def test_listener_install_guard(self):
        self.assertIn("__wr_spec_installed__", INSTALL_LISTENER_SCRIPT)
        self.assertIn("prerenderingchange", INSTALL_LISTENER_SCRIPT)

    def test_harvest_constant(self):
        self.assertIn("__wr_spec__", HARVEST_LOG_SCRIPT)


class TestParseLog(unittest.TestCase):

    def test_basic(self):
        log = parse_log({
            "events": [{"kind": "prerenderingchange", "prerendering": False}],
            "fires": {"analytics": 1},
        })
        self.assertEqual(len(log.events), 1)
        self.assertEqual(log.fires["analytics"], 1)

    def test_rejects_non_dict(self):
        with self.assertRaises(SpeculationRulesError):
            parse_log("nope")

    def test_rejects_bad_inner_types(self):
        with self.assertRaises(SpeculationRulesError):
            parse_log({"events": "x", "fires": {}})


class TestAssertActivated(unittest.TestCase):

    def test_pass(self):
        assert_activated(parse_log({
            "events": [{"kind": "prerenderingchange", "prerendering": False}],
            "fires": {},
        }))

    def test_fail_no_event(self):
        with self.assertRaises(SpeculationRulesError):
            assert_activated(parse_log({"events": [], "fires": {}}))

    def test_fail_still_prerendering(self):
        with self.assertRaises(SpeculationRulesError):
            assert_activated(parse_log({
                "events": [{"kind": "prerenderingchange", "prerendering": True}],
                "fires": {},
            }))


class TestAssertNoDoubleFire(unittest.TestCase):

    def test_pass(self):
        assert_no_double_fire(
            parse_log({"events": [], "fires": {"a": 1, "b": 0}}),
            names=["a", "b"],
        )

    def test_fail(self):
        with self.assertRaises(SpeculationRulesError):
            assert_no_double_fire(
                parse_log({"events": [], "fires": {"a": 2}}),
                names=["a"],
            )

    def test_empty_names(self):
        with self.assertRaises(SpeculationRulesError):
            assert_no_double_fire(PrerenderLog(), names=[])


class TestAssertFireCount(unittest.TestCase):

    def test_pass(self):
        assert_fire_count(
            parse_log({"events": [], "fires": {"a": 3}}),
            name="a", expected=3,
        )

    def test_fail(self):
        with self.assertRaises(SpeculationRulesError):
            assert_fire_count(
                parse_log({"events": [], "fires": {"a": 2}}),
                name="a", expected=1,
            )


if __name__ == "__main__":
    unittest.main()
