"""Unit tests for je_web_runner.utils.cross_tab_sync."""
import json
import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.cross_tab_sync.sync_assertions import (
    CrossTabSyncError,
    assert_state_propagates,
    broadcast_message,
    collect_broadcast_messages,
    get_storage_value,
    install_broadcast_recorder,
    post_message_to_page,
    set_storage_value,
    wait_for_broadcast,
    wait_for_storage,
)


class FakeStoragePage:
    """Minimal Playwright Page double that emulates localStorage."""

    def __init__(self, initial=None):
        self.local = dict(initial or {})
        self.session = {}
        self.evaluate_calls = []

    def evaluate(self, script, arg=None):
        self.evaluate_calls.append((script, arg))
        if "setItem" in script:
            store_attr = "local" if "localStorage" in script else "session"
            getattr(self, store_attr)[arg["key"]] = arg["raw"]
            return None
        if "getItem" in script:
            store_attr = "local" if "localStorage" in script else "session"
            return getattr(self, store_attr).get(arg)
        if "BroadcastChannel" in script:
            return True
        if "postMessage" in script:
            return None
        return None


class TestStorageHelpers(unittest.TestCase):

    def test_set_and_get_roundtrip(self):
        page = FakeStoragePage()
        set_storage_value(page, "cart", {"items": 3})
        self.assertEqual(get_storage_value(page, "cart"), {"items": 3})

    def test_session_storage(self):
        page = FakeStoragePage()
        set_storage_value(page, "k", "v", storage="sessionStorage")
        self.assertEqual(get_storage_value(page, "k", storage="sessionStorage"),
                         "v")

    def test_invalid_storage_name(self):
        page = FakeStoragePage()
        with self.assertRaises(CrossTabSyncError):
            set_storage_value(page, "k", 1, storage="cookieJar")

    def test_no_page_raises(self):
        with self.assertRaises(CrossTabSyncError):
            set_storage_value(None, "k", 1)
        with self.assertRaises(CrossTabSyncError):
            get_storage_value(None, "k")

    def test_non_json_value_returns_raw(self):
        page = FakeStoragePage()
        page.local["raw"] = "not json"
        self.assertEqual(get_storage_value(page, "raw"), "not json")

    def test_set_propagates_evaluate_failure(self):
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("boom")
        with self.assertRaises(CrossTabSyncError):
            set_storage_value(page, "k", 1)


class TestWaitForStorage(unittest.TestCase):

    def test_returns_immediately_if_present(self):
        page = FakeStoragePage()
        page.local["greeting"] = json.dumps("hi")
        result = wait_for_storage(
            page, "greeting", "hi",
            timeout=2, poll_interval=0.01,
            sleep_fn=lambda _s: None,
        )
        self.assertEqual(result, "hi")

    def test_polls_until_visible(self):
        page = FakeStoragePage()
        sleeps = {"count": 0}

        def fake_sleep(_s):
            sleeps["count"] += 1
            if sleeps["count"] == 2:
                page.local["k"] = json.dumps(99)

        clock = {"now": 0.0}

        def fake_time():
            return clock["now"]

        def wrapped_sleep(s):
            clock["now"] += s
            fake_sleep(s)

        result = wait_for_storage(
            page, "k", 99,
            timeout=5, poll_interval=0.1,
            sleep_fn=wrapped_sleep, time_fn=fake_time,
        )
        self.assertEqual(result, 99)

    def test_times_out(self):
        page = FakeStoragePage()
        clock = {"now": 0.0}

        def fake_time():
            return clock["now"]

        def fake_sleep(s):
            clock["now"] += s

        with self.assertRaises(CrossTabSyncError):
            wait_for_storage(
                page, "k", "x",
                timeout=1, poll_interval=0.5,
                sleep_fn=fake_sleep, time_fn=fake_time,
            )

    def test_invalid_timeout_raises(self):
        page = FakeStoragePage()
        with self.assertRaises(CrossTabSyncError):
            wait_for_storage(page, "k", "x", timeout=0)


class TestBroadcastRecorder(unittest.TestCase):

    def test_install_calls_evaluate(self):
        page = MagicMock()
        install_broadcast_recorder(page, "events")
        page.evaluate.assert_called_once()
        self.assertEqual(page.evaluate.call_args.args[1], "events")

    def test_empty_channel_name_raises(self):
        page = MagicMock()
        with self.assertRaises(CrossTabSyncError):
            install_broadcast_recorder(page, "")

    def test_eval_failure_wraps(self):
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("nope")
        with self.assertRaises(CrossTabSyncError):
            install_broadcast_recorder(page, "x")


class TestBroadcastMessage(unittest.TestCase):

    def test_invokes_eval(self):
        page = MagicMock()
        broadcast_message(page, "ch", {"event": "go"})
        page.evaluate.assert_called_once()
        payload = page.evaluate.call_args.args[1]
        self.assertEqual(payload["channelName"], "ch")
        self.assertEqual(payload["payload"]["event"], "go")

    def test_failure_wrapped(self):
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("no")
        with self.assertRaises(CrossTabSyncError):
            broadcast_message(page, "ch", {})


class TestCollectAndWaitBroadcast(unittest.TestCase):

    def _page_returning(self, log):
        page = MagicMock()
        page.evaluate.return_value = log
        return page

    def test_collect_returns_log(self):
        page = self._page_returning([{"data": "x", "receivedAt": 1}])
        result = collect_broadcast_messages(page, "ch")
        self.assertEqual(result, [{"data": "x", "receivedAt": 1}])

    def test_collect_falls_back_to_empty(self):
        page = self._page_returning(None)
        self.assertEqual(collect_broadcast_messages(page, "ch"), [])

    def test_wait_finds_matching(self):
        page = self._page_returning([
            {"data": {"event": "skip"}, "receivedAt": 1},
            {"data": {"event": "buy"}, "receivedAt": 2},
        ])
        result = wait_for_broadcast(
            page, "ch",
            matcher=lambda d: isinstance(d, dict) and d.get("event") == "buy",
            timeout=1, poll_interval=0.01,
            sleep_fn=lambda _s: None,
        )
        self.assertEqual(result["data"]["event"], "buy")

    def test_wait_times_out(self):
        page = self._page_returning([])
        clock = {"now": 0.0}

        def fake_time():
            return clock["now"]

        def fake_sleep(s):
            clock["now"] += s

        with self.assertRaises(CrossTabSyncError):
            wait_for_broadcast(
                page, "ch",
                matcher=lambda _d: False,
                timeout=1, poll_interval=0.5,
                sleep_fn=fake_sleep, time_fn=fake_time,
            )


class TestAssertStatePropagates(unittest.TestCase):

    def test_all_listeners_see_value(self):
        source = FakeStoragePage()
        listener_a = FakeStoragePage()
        listener_b = FakeStoragePage()

        # Mimic BroadcastChannel propagation: when source sets, both
        # listeners pick it up after a short delay.
        sleeps = {"n": 0}

        def fake_sleep(_s):
            sleeps["n"] += 1
            if sleeps["n"] == 1:
                listener_a.local["cart"] = source.local["cart"]
            elif sleeps["n"] == 2:
                listener_b.local["cart"] = source.local["cart"]

        result = assert_state_propagates(
            source, [listener_a, listener_b],
            key="cart", value={"items": 5},
            timeout=5, poll_interval=0.1,
            sleep_fn=fake_sleep,
        )
        self.assertEqual(set(result.propagated_to), {0, 1})

    def test_timeout_lists_missing_tabs(self):
        source = FakeStoragePage()
        listener = FakeStoragePage()
        clock = {"now": 0.0}

        def fake_time():
            return clock["now"]

        def fake_sleep(s):
            clock["now"] += s

        with self.assertRaises(CrossTabSyncError) as cm:
            assert_state_propagates(
                source, [listener],
                key="cart", value=1,
                timeout=1, poll_interval=0.5,
                sleep_fn=fake_sleep, time_fn=fake_time,
            )
        self.assertIn("[0]", str(cm.exception))

    def test_no_source_raises(self):
        with self.assertRaises(CrossTabSyncError):
            assert_state_propagates(None, [FakeStoragePage()], key="k", value=1)

    def test_no_listeners_raises(self):
        with self.assertRaises(CrossTabSyncError):
            assert_state_propagates(FakeStoragePage(), [], key="k", value=1)


class TestPostMessage(unittest.TestCase):

    def test_passes_data_and_origin(self):
        page = MagicMock()
        post_message_to_page(page, {"x": 1}, target_origin="https://x")
        payload = page.evaluate.call_args.args[1]
        self.assertEqual(payload["payload"], {"x": 1})
        self.assertEqual(payload["origin"], "https://x")

    def test_failure_wrapped(self):
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("no")
        with self.assertRaises(CrossTabSyncError):
            post_message_to_page(page, {})


if __name__ == "__main__":
    unittest.main()
