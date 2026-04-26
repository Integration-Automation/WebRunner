import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.api_mock import (
    ApiMockError,
    MockRouter,
    register_route,
)
from je_web_runner.utils.api_mock.router import global_router, reset_global_router


class TestMockRouter(unittest.TestCase):

    def test_exact_url_match(self):
        router = MockRouter()
        router.add("GET", "https://example.com/api/v1/users", body={"ok": True})
        match = router.match("GET", "https://example.com/api/v1/users")
        self.assertIsNotNone(match)

    def test_glob_url_match(self):
        router = MockRouter()
        router.add("GET", "https://api.example.com/users/*", body={"id": 1})
        match = router.match("GET", "https://api.example.com/users/42")
        self.assertIsNotNone(match)

    def test_regex_url_match(self):
        router = MockRouter()
        router.add("POST", "re:/api/v\\d+/items", body={})
        match = router.match("POST", "https://example.com/api/v3/items")
        self.assertIsNotNone(match)

    def test_method_filter(self):
        router = MockRouter()
        router.add("POST", "/x", body={})
        self.assertIsNone(router.match("GET", "/x"))

    def test_wildcard_method(self):
        router = MockRouter()
        router.add("*", "/x", body={})
        self.assertIsNotNone(router.match("DELETE", "/x"))

    def test_times_limited(self):
        router = MockRouter()
        router.add("GET", "/once", body={}, times=1)
        self.assertIsNotNone(router.match("GET", "/once"))
        self.assertIsNone(router.match("GET", "/once"))

    def test_calls_recorded(self):
        router = MockRouter()
        router.add("GET", "/x", body={})
        router.match("GET", "/x")
        router.match("POST", "/y")
        self.assertEqual(router.calls(), [("GET", "/x"), ("POST", "/y")])

    def test_invalid_config_raises(self):
        router = MockRouter()
        with self.assertRaises(ApiMockError):
            router.add("", "/x")
        with self.assertRaises(ApiMockError):
            router.add("GET", "")


class TestPlaywrightAttach(unittest.TestCase):

    def test_attach_calls_page_route(self):
        page = MagicMock()
        router = MockRouter()
        router.add("GET", "/api/x", body={"ok": True})
        router.attach_to_page(page)
        page.route.assert_called_once()
        args, _kwargs = page.route.call_args
        self.assertEqual(args[0], "**/*")
        # Invoke handler manually
        handler = args[1]
        request = MagicMock(method="GET", url="/api/x")
        route = MagicMock()
        handler(route, request)
        route.fulfill.assert_called_once()

    def test_attach_to_non_playwright_raises(self):
        router = MockRouter()
        with self.assertRaises(ApiMockError):
            router.attach_to_page(object())


class TestGlobalRouter(unittest.TestCase):

    def setUp(self):
        reset_global_router()

    def test_register_route_uses_singleton(self):
        register_route("GET", "/global", body={"ok": True})
        match = global_router().match("GET", "/global")
        self.assertIsNotNone(match)

    def test_reset_clears_state(self):
        register_route("GET", "/x")
        global_router().match("GET", "/x")
        reset_global_router()
        self.assertEqual(global_router().calls(), [])
        self.assertIsNone(global_router().match("GET", "/x"))


if __name__ == "__main__":
    unittest.main()
