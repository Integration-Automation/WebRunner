"""Unit tests for je_web_runner.utils.otel_bridge."""
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.otel_bridge.trace_bridge import (
    TraceBridgeError,
    TraceContext,
    bridged_span_playwright,
    bridged_span_selenium,
    clear_headers_playwright,
    clear_headers_selenium,
    current_otel_context,
    inject_headers_playwright,
    inject_headers_selenium,
    parse_traceparent,
    random_trace_context,
    trace_link,
)


class TestTraceContext(unittest.TestCase):

    def test_traceparent_format(self):
        ctx = TraceContext(
            trace_id="a" * 32, span_id="b" * 16, sampled=True,
        )
        self.assertEqual(ctx.to_traceparent(), f"00-{'a'*32}-{'b'*16}-01")

    def test_traceparent_not_sampled(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16, sampled=False)
        self.assertTrue(ctx.to_traceparent().endswith("-00"))

    def test_as_headers_includes_tracestate(self):
        ctx = TraceContext(
            trace_id="a" * 32, span_id="b" * 16, tracestate="vendor=x",
        )
        headers = ctx.as_headers()
        self.assertIn("traceparent", headers)
        self.assertEqual(headers["tracestate"], "vendor=x")

    def test_as_headers_without_tracestate(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        self.assertNotIn("tracestate", ctx.as_headers())


class TestRandomContext(unittest.TestCase):

    def test_random_returns_valid_hex(self):
        ctx = random_trace_context()
        self.assertEqual(len(ctx.trace_id), 32)
        self.assertEqual(len(ctx.span_id), 16)
        # round-trip through parse_traceparent
        parsed = parse_traceparent(ctx.to_traceparent())
        self.assertEqual(parsed.trace_id, ctx.trace_id)
        self.assertEqual(parsed.span_id, ctx.span_id)


class TestParseTraceparent(unittest.TestCase):

    def test_round_trip(self):
        original = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        parsed = parse_traceparent(original.to_traceparent())
        self.assertEqual(parsed.trace_id, original.trace_id)

    def test_malformed_raises(self):
        with self.assertRaises(TraceBridgeError):
            parse_traceparent("garbage")
        with self.assertRaises(TraceBridgeError):
            parse_traceparent("00-tooshort-tooshort-01")


class TestInjectSelenium(unittest.TestCase):

    def test_calls_cdp_with_headers(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        driver = MagicMock()
        inject_headers_selenium(driver, ctx)
        calls = [c.args for c in driver.execute_cdp_cmd.call_args_list]
        # at least one Network.setExtraHTTPHeaders call
        set_calls = [c for c in calls if c[0] == "Network.setExtraHTTPHeaders"]
        self.assertEqual(len(set_calls), 1)
        self.assertIn("traceparent", set_calls[0][1]["headers"])

    def test_no_driver_raises(self):
        ctx = random_trace_context()
        with self.assertRaises(TraceBridgeError):
            inject_headers_selenium(None, ctx)

    def test_driver_without_cdp_raises(self):
        ctx = random_trace_context()
        driver = MagicMock(spec=["foo"])  # no execute_cdp_cmd
        with self.assertRaises(TraceBridgeError):
            inject_headers_selenium(driver, ctx)

    def test_cdp_error_wraps(self):
        ctx = random_trace_context()
        driver = MagicMock()
        driver.execute_cdp_cmd.side_effect = RuntimeError("boom")
        with self.assertRaises(TraceBridgeError):
            inject_headers_selenium(driver, ctx)

    def test_clear_is_noop_on_missing_cdp(self):
        clear_headers_selenium(None)
        driver = MagicMock(spec=["foo"])
        clear_headers_selenium(driver)


class TestInjectPlaywright(unittest.TestCase):

    def test_set_extra_http_headers(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        page = MagicMock()
        inject_headers_playwright(page, ctx)
        page.set_extra_http_headers.assert_called_once()
        payload = page.set_extra_http_headers.call_args.args[0]
        self.assertIn("traceparent", payload)

    def test_no_page_raises(self):
        with self.assertRaises(TraceBridgeError):
            inject_headers_playwright(None, random_trace_context())

    def test_page_without_setter_raises(self):
        page = MagicMock(spec=[])
        with self.assertRaises(TraceBridgeError):
            inject_headers_playwright(page, random_trace_context())

    def test_clear(self):
        page = MagicMock()
        clear_headers_playwright(page)
        page.set_extra_http_headers.assert_called_once_with({})


class TestCurrentOtelContext(unittest.TestCase):

    def test_returns_none_without_otel(self):
        # Pretend OTel isn't importable.
        import builtins
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "opentelemetry":
                raise ImportError("simulated")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            self.assertIsNone(current_otel_context())


class TestBridgedSpan(unittest.TestCase):

    def test_selenium_context_manager_injects_and_clears(self):
        driver = MagicMock()
        with bridged_span_selenium(driver, "test_action") as ctx:
            self.assertEqual(len(ctx.trace_id), 32)
        # Should be called at least twice: enable + set + clear
        names = [c.args[0] for c in driver.execute_cdp_cmd.call_args_list]
        self.assertIn("Network.setExtraHTTPHeaders", names)

    def test_playwright_context_manager_clears(self):
        page = MagicMock()
        with bridged_span_playwright(page, "click"):
            pass
        # at least one set and one reset call
        self.assertGreaterEqual(page.set_extra_http_headers.call_count, 2)
        last_call = page.set_extra_http_headers.call_args_list[-1].args[0]
        self.assertEqual(last_call, {})

    def test_fallback_context_used_without_otel(self):
        import builtins
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "opentelemetry":
                raise ImportError("simulated")
            return original_import(name, *args, **kwargs)

        fallback = TraceContext(trace_id="c" * 32, span_id="d" * 16)
        with patch("builtins.__import__", side_effect=fake_import):
            page = MagicMock()
            with bridged_span_playwright(page, "x", fallback_context=fallback) as ctx:
                self.assertEqual(ctx.trace_id, fallback.trace_id)


class TestTraceLink(unittest.TestCase):

    def test_jaeger_link(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        link = trace_link(ctx, jaeger_base="https://jaeger.local/")
        self.assertEqual(link, f"https://jaeger.local/trace/{'a'*32}")

    def test_tempo_link(self):
        ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16)
        link = trace_link(ctx, tempo_base="https://tempo.local")
        self.assertIn("a" * 32, link)

    def test_no_base_returns_none(self):
        self.assertIsNone(trace_link(random_trace_context()))


if __name__ == "__main__":
    unittest.main()
