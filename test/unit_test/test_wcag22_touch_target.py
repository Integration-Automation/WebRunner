"""Unit tests for je_web_runner.utils.wcag22_touch_target."""
import unittest

from je_web_runner.utils.wcag22_touch_target.touch import (
    HARVEST_SCRIPT,
    MIN_SIZE_CSS_PX,
    Wcag22TouchTargetError,
    assert_no_violations,
    audit,
    parse_targets,
)


def _t(**kw):
    base = {
        "tag": "button", "role": "", "type": "",
        "width": 30, "height": 30, "x": 0, "y": 0,
        "label": "btn",
        "isInlineInText": False, "isUserAgentControl": False,
    }
    base.update(kw)
    return base


class TestParse(unittest.TestCase):

    def test_basic(self):
        targets = parse_targets([_t(label="ok")])
        self.assertEqual(targets[0].label, "ok")

    def test_script_constant(self):
        self.assertIn("getBoundingClientRect", HARVEST_SCRIPT)

    def test_skips_non_dict(self):
        targets = parse_targets([_t(), "string"])
        self.assertEqual(len(targets), 1)

    def test_rejects_non_list(self):
        with self.assertRaises(Wcag22TouchTargetError):
            parse_targets("nope")


class TestAudit(unittest.TestCase):

    def test_pass_large_enough(self):
        v = audit(parse_targets([_t(width=24, height=24)]))
        self.assertEqual(v, [])

    def test_inline_text_exempt(self):
        v = audit(parse_targets([_t(width=10, height=10, isInlineInText=True)]))
        self.assertEqual(v, [])

    def test_user_agent_exempt(self):
        v = audit(parse_targets([_t(tag="input", width=10, height=10,
                                    isUserAgentControl=True)]))
        self.assertEqual(v, [])

    def test_spacing_circle_exempt(self):
        # only one element → spacing-circle automatically passes
        v = audit(parse_targets([_t(width=20, height=20)]))
        # alone, no neighbours within 24px, so we get the spacing exemption
        self.assertEqual(v, [])

    def test_dense_cluster_violates(self):
        # two small adjacent buttons within 24px center-to-center
        v = audit(parse_targets([
            _t(label="a", width=20, height=20, x=0, y=0),
            _t(label="b", width=20, height=20, x=10, y=0),
        ]))
        self.assertEqual(len(v), 2)

    def test_min_size_constant(self):
        self.assertEqual(MIN_SIZE_CSS_PX, 24)

    def test_non_list(self):
        with self.assertRaises(Wcag22TouchTargetError):
            audit("nope")


class TestAssert(unittest.TestCase):

    def test_pass(self):
        assert_no_violations([])

    def test_fail(self):
        v = audit(parse_targets([
            _t(label="a", width=20, height=20, x=0, y=0),
            _t(label="b", width=20, height=20, x=10, y=0),
        ]))
        with self.assertRaises(Wcag22TouchTargetError):
            assert_no_violations(v)


if __name__ == "__main__":
    unittest.main()
