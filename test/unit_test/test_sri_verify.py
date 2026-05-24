"""Unit tests for je_web_runner.utils.sri_verify."""
import unittest

from je_web_runner.utils.sri_verify.verify import (
    ResourceTag,
    SriFinding,
    SriVerifyError,
    Verdict,
    assert_all_ok,
    compute_integrity,
    parse_html,
    verify_html,
    verify_tag,
)


_JS = b"console.log('hi');"
_GOOD = compute_integrity(_JS, "sha384")


class TestComputeIntegrity(unittest.TestCase):

    def test_sha384(self):
        out = compute_integrity(b"hello", "sha384")
        self.assertTrue(out.startswith("sha384-"))

    def test_sha256(self):
        out = compute_integrity(b"hello", "sha256")
        self.assertTrue(out.startswith("sha256-"))

    def test_unknown_alg(self):
        with self.assertRaises(SriVerifyError):
            compute_integrity(b"x", "blake3")

    def test_payload_must_be_bytes(self):
        with self.assertRaises(SriVerifyError):
            compute_integrity("text", "sha256")  # type: ignore[arg-type]


class TestParseHtml(unittest.TestCase):

    def test_script_with_integrity(self):
        html = (
            f'<script src="https://cdn/x.js" integrity="{_GOOD}" '
            'crossorigin="anonymous"></script>'
        )
        tags = parse_html(html)
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].tag, "script")
        self.assertEqual(tags[0].integrity, _GOOD)
        self.assertEqual(tags[0].crossorigin, "anonymous")

    def test_link_stylesheet(self):
        html = '<link rel="stylesheet" href="/a.css" integrity="sha256-abc">'
        tags = parse_html(html)
        self.assertEqual(tags[0].tag, "link")

    def test_link_non_stylesheet_skipped(self):
        html = '<link rel="icon" href="/favicon.ico">'
        self.assertEqual(parse_html(html), [])

    def test_script_without_src_skipped(self):
        html = "<script>console.log(1)</script>"
        self.assertEqual(parse_html(html), [])

    def test_rejects_non_string(self):
        with self.assertRaises(SriVerifyError):
            parse_html(123)  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test


class TestVerifyTag(unittest.TestCase):

    def test_missing_integrity(self):
        tag = ResourceTag(tag="script", url="https://cdn/x.js")
        finding = verify_tag(tag)
        self.assertEqual(finding.verdict, Verdict.MISSING)

    def test_weak_alg(self):
        tag = ResourceTag(
            tag="script", url="https://cdn/x.js",
            integrity="sha1-abcdef==", crossorigin="anonymous",
        )
        self.assertEqual(verify_tag(tag).verdict, Verdict.WEAK_ALG)

    def test_unknown_format(self):
        _tag = ResourceTag(
            tag="script", url="https://cdn/x.js",
            integrity="not-an-integrity",
        )
        # 'not-an-integrity' parses as alg='not', so it falls into WEAK_ALG
        # (not in strong set). Use a value with no dash for UNKNOWN_FORMAT:
        tag2 = ResourceTag(
            tag="script", url="https://cdn/x.js", integrity="garbage",
        )
        self.assertEqual(verify_tag(tag2).verdict, Verdict.UNKNOWN_FORMAT)

    def test_cross_origin_needs_crossorigin(self):
        tag = ResourceTag(
            tag="script", url="https://cdn/x.js", integrity=_GOOD,
        )
        self.assertEqual(verify_tag(tag).verdict, Verdict.NO_CROSSORIGIN)

    def test_same_origin_no_crossorigin_ok(self):
        tag = ResourceTag(tag="script", url="/local.js", integrity=_GOOD)
        self.assertEqual(verify_tag(tag).verdict, Verdict.OK)

    def test_payload_match(self):
        tag = ResourceTag(
            tag="script", url="https://cdn/x.js",
            integrity=_GOOD, crossorigin="anonymous",
        )
        self.assertEqual(verify_tag(tag, payload=_JS).verdict, Verdict.OK)

    def test_payload_mismatch(self):
        tag = ResourceTag(
            tag="script", url="https://cdn/x.js",
            integrity=_GOOD, crossorigin="anonymous",
        )
        self.assertEqual(
            verify_tag(tag, payload=b"different").verdict,
            Verdict.HASH_MISMATCH,
        )

    def test_disable_crossorigin_check(self):
        tag = ResourceTag(
            tag="script", url="https://cdn/x.js", integrity=_GOOD,
        )
        self.assertEqual(
            verify_tag(tag, require_crossorigin=False).verdict, Verdict.OK,
        )

    def test_rejects_non_tag(self):
        with self.assertRaises(SriVerifyError):
            verify_tag("nope")  # type: ignore[arg-type]


class TestVerifyHtml(unittest.TestCase):

    def test_no_provider(self):
        html = (
            f'<script src="https://cdn/x.js" integrity="{_GOOD}" '
            'crossorigin="anonymous"></script>'
            '<script src="/local.js"></script>'
        )
        findings = verify_html(html)
        verdicts = {f.verdict for f in findings}
        self.assertIn(Verdict.OK, verdicts)
        self.assertIn(Verdict.MISSING, verdicts)

    def test_with_provider(self):
        html = (
            f'<script src="https://cdn/x.js" integrity="{_GOOD}" '
            'crossorigin="anonymous"></script>'
        )
        findings = verify_html(html, payload_provider=lambda _u: _JS)
        self.assertEqual(findings[0].verdict, Verdict.OK)

    def test_provider_returning_bad_payload(self):
        html = (
            f'<script src="https://cdn/x.js" integrity="{_GOOD}" '
            'crossorigin="anonymous"></script>'
        )
        with self.assertRaises(SriVerifyError):
            verify_html(html, payload_provider=lambda _u: "not bytes")

    def test_provider_raising(self):
        html = (
            f'<script src="https://cdn/x.js" integrity="{_GOOD}" '
            'crossorigin="anonymous"></script>'
        )
        def boom(_):
            raise RuntimeError("network down")
        with self.assertRaises(SriVerifyError):
            verify_html(html, payload_provider=boom)


class TestAssertAllOk(unittest.TestCase):

    def test_pass(self):
        assert_all_ok([SriFinding(tag="script", url="/x", verdict=Verdict.OK)])

    def test_fail(self):
        with self.assertRaises(SriVerifyError):
            assert_all_ok([
                SriFinding(tag="script", url="/x", verdict=Verdict.MISSING),
            ])


if __name__ == "__main__":
    unittest.main()
