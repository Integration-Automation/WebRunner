"""Unit tests for je_web_runner.utils.cookie_store_api."""
import unittest

from je_web_runner.utils.cookie_store_api.store import (
    CookieStoreApiError,
    GET_ALL_SCRIPT,
    HARVEST_CHANGES_SCRIPT,
    assert_change_for,
    assert_cookie_absent,
    assert_cookie_present,
    assert_secure_only,
    install_change_listener_script,
    parse_change_events,
    parse_cookies,
)


class TestScripts(unittest.TestCase):

    def test_get_all_uses_api(self):
        self.assertIn("cookieStore.getAll", GET_ALL_SCRIPT)

    def test_listener_install_guard(self):
        js = install_change_listener_script()
        self.assertIn("__wr_cs_installed__", js)
        self.assertIn("addEventListener", js)

    def test_harvest_const(self):
        self.assertIn("__wr_cs__", HARVEST_CHANGES_SCRIPT)


class TestParseCookies(unittest.TestCase):

    def test_basic(self):
        cookies = parse_cookies([
            {"name": "sid", "value": "abc", "secure": True, "sameSite": "lax"},
        ])
        self.assertEqual(cookies[0].name, "sid")
        self.assertEqual(cookies[0].same_site, "lax")

    def test_skips_nameless(self):
        self.assertEqual(parse_cookies([{}, {"value": "x"}]), [])

    def test_rejects_non_list(self):
        with self.assertRaises(CookieStoreApiError):
            parse_cookies({"x": 1})


class TestParseChangeEvents(unittest.TestCase):

    def test_basic(self):
        events = parse_change_events([
            {"changed": [{"name": "a", "value": "1"}],
             "deleted": ["b"], "timestamp_ms": 100},
        ])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].changed[0].name, "a")
        self.assertEqual(events[0].deleted, ["b"])

    def test_rejects_non_list(self):
        with self.assertRaises(CookieStoreApiError):
            parse_change_events("nope")


class TestAssertPresent(unittest.TestCase):

    def _cookies(self):
        return parse_cookies([{"name": "sid", "value": "abc"}])

    def test_pass_no_value(self):
        assert_cookie_present(self._cookies(), name="sid")

    def test_pass_with_value(self):
        assert_cookie_present(self._cookies(), name="sid", value="abc")

    def test_value_mismatch(self):
        with self.assertRaises(CookieStoreApiError):
            assert_cookie_present(self._cookies(), name="sid", value="xyz")

    def test_missing(self):
        with self.assertRaises(CookieStoreApiError):
            assert_cookie_present(self._cookies(), name="missing")

    def test_empty_name(self):
        with self.assertRaises(CookieStoreApiError):
            assert_cookie_present(self._cookies(), name="")


class TestAssertAbsent(unittest.TestCase):

    def test_pass(self):
        assert_cookie_absent(parse_cookies([{"name": "other"}]), name="sid")

    def test_fails(self):
        with self.assertRaises(CookieStoreApiError):
            assert_cookie_absent(parse_cookies([{"name": "sid"}]), name="sid")


class TestAssertChange(unittest.TestCase):

    def test_changed_match(self):
        events = parse_change_events([
            {"changed": [{"name": "sid", "value": "v"}], "deleted": []},
        ])
        assert_change_for(events, name="sid")

    def test_deleted_match(self):
        events = parse_change_events([
            {"changed": [], "deleted": ["sid"]},
        ])
        assert_change_for(events, name="sid")

    def test_miss(self):
        with self.assertRaises(CookieStoreApiError):
            assert_change_for([], name="sid")


class TestAssertSecure(unittest.TestCase):

    def test_pass(self):
        assert_secure_only(parse_cookies([{"name": "a", "secure": True}]))

    def test_fail(self):
        with self.assertRaises(CookieStoreApiError):
            assert_secure_only(parse_cookies([
                {"name": "a", "secure": True},
                {"name": "b", "secure": False},
            ]))


if __name__ == "__main__":
    unittest.main()
