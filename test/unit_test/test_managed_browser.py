"""Managed lifecycle and pre-page guards with fake Playwright; never launch a browser."""
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.agent._managed_guard import ContextGuard, ManagedBrowserError
from je_web_runner.utils.agent.managed_browser import ManagedBrowserSession
from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent.types import AgentAction
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_element_wrapper import playwright_element_wrapper


@pytest.fixture
def opened():
    """Use real owner/guard/loopback transport with a fake installed runtime and page."""
    events = {}
    page_events = {}
    page = MagicMock()
    page.url = "about:blank"
    page.on.side_effect = lambda name, callback: page_events.setdefault(name, []).append(callback)
    context = MagicMock()
    context.on.side_effect = lambda name, callback: events.setdefault(name, []).append(callback)

    def new_page():
        context.route.assert_called_once()
        context.route_web_socket.assert_called_once()
        assert context.add_init_script.call_count == 2
        for callback in events["page"]:
            callback(page)
        return page

    context.new_page.side_effect = new_page
    browser = MagicMock()
    browser.new_context.return_value = context
    runtime = MagicMock()
    runtime.chromium.launch.return_value = browser
    factory = MagicMock()
    factory.return_value.start.return_value = runtime
    with patch.object(pw_module, "_require_playwright", return_value=factory):
        instance = ManagedBrowserSession.open(BrowserOriginPolicy(("https://allowed.test",)))
    try:
        yield instance, runtime, browser, context, page, events, page_events
    finally:
        if not instance.closed:
            # Cleanup-failure tests deliberately leave a sticky unconfirmed state.
            try:
                instance.close()
            except ManagedBrowserError as error:
                assert error.reason == "cleanup_unconfirmed"


def test_pre_page_setup_private_proxy_and_fresh_element_state(opened):
    instance, runtime, browser, _, page, _, _ = opened
    launch = runtime.chromium.launch.call_args.kwargs
    assert launch["headless"] is True
    assert launch["chromium_sandbox"] is True
    assert launch["proxy"]["bypass"] == "<-loopback>"
    assert launch["proxy"]["password"]
    assert "--disable-quic" in launch["args"]
    assert "--disable-http2" in launch["args"]
    assert browser.new_context.call_args.kwargs == {
        "accept_downloads": False, "service_workers": "block", "permissions": [], "ignore_https_errors": False,
    }
    assert instance._owner.element_wrapper is not playwright_element_wrapper
    assert instance.url == "about:blank"
    instance.perform(AgentAction("navigate", value="https://allowed.test/start"))
    page.goto.assert_called_once_with("https://allowed.test/start", wait_until="domcontentloaded")


def test_outside_navigation_refused_before_effect(opened):
    instance, _, _, _, page, _, _ = opened
    with pytest.raises(Exception, match="outside allowed origins"):
        instance.perform(AgentAction("navigate", value="https://blocked.test/private?secret=x"))
    page.goto.assert_not_called()
    assert not instance.closed


def test_request_guard_checks_origin_and_page_ownership(opened):
    instance, _, _, context, page, _, _ = opened
    callback = context.route.call_args.args[1]
    route = MagicMock()
    route.request.url = "https://allowed.test/resource"
    route.request.frame.page = page
    callback(route)
    route.continue_.assert_called_once_with()
    route.request.url = "https://blocked.test/resource"
    callback(route)
    assert route.abort.call_count == 1
    route.request.url = "https://allowed.test/resource"
    route.request.frame.page = MagicMock()
    callback(route)
    assert route.abort.call_count == 2
    assert instance._guard.fault == ""


def test_websocket_never_connects(opened):
    _, _, _, context, _, _, _ = opened
    route = MagicMock()
    context.route_web_socket.call_args.args[1](route)
    route.close.assert_called_once()
    route.connect_to_server.assert_not_called()


@pytest.mark.parametrize("event,reason", [
    ("dialog", "human_review_required"), ("download", "download_blocked"),
    ("filechooser", "upload_blocked"), ("crash", "page_crashed"), ("close", "page_closed"),
])
def test_unexpected_ui_retires_network_and_blocks_followup(opened, event, reason):
    instance, _, _, _, page, _, page_events = opened
    payload = MagicMock()
    for callback in page_events[event]:
        callback(payload)
    assert instance._proxy.closed
    with pytest.raises(ManagedBrowserError) as failure:
        instance.perform(AgentAction("click", selector="#submit"))
    assert failure.value.reason == reason
    page.locator.assert_not_called()
    if event == "dialog":
        payload.dismiss.assert_called_once()
        payload.accept.assert_not_called()
    if event == "download":
        payload.cancel.assert_called_once()


def test_popup_retired_without_adopting_page(opened):
    instance, _, _, _, page, events, _ = opened
    popup = MagicMock()
    for callback in events["page"]:
        callback(popup)
    popup.close.assert_called_once_with(run_before_unload=False)
    assert instance._guard.page is page
    assert instance._guard.fault == "popup_blocked"
    assert instance._proxy.closed


def test_failed_effect_is_uncertain_once_and_contains_no_raw_error(opened):
    instance, _, _, _, page, _, _ = opened
    page.goto.side_effect = RuntimeError("private entered password:SECRET")
    with pytest.raises(ManagedBrowserError) as failure:
        instance.perform(AgentAction("navigate", value="https://allowed.test"))
    assert failure.value.uncertain
    assert "SECRET" not in str(failure.value)
    assert failure.value.__suppress_context__
    assert page.goto.call_count == 1
    assert instance._proxy.closed
    with pytest.raises(ManagedBrowserError):
        instance.perform(AgentAction("navigate", value="https://allowed.test"))
    assert page.goto.call_count == 1


def test_event_during_effect_is_reported_uncertain(opened):
    instance, _, _, _, page, _, page_events = opened
    page.goto.side_effect = lambda *_args, **_kwargs: page_events["dialog"][0](MagicMock())
    with pytest.raises(ManagedBrowserError) as failure:
        instance.perform(AgentAction("navigate", value="https://allowed.test"))
    assert failure.value.reason == "human_review_required"
    assert failure.value.uncertain
    assert page.goto.call_count == 1


def test_explicit_form_readback_refuses_secret_result(opened):
    instance, _, _, _, _, _, _ = opened
    with patch.object(instance._session, "_find") as find:
        find.return_value.evaluate.return_value = "filled value"
        assert instance.read_value("#name") == "filled value"
        find.return_value.evaluate.return_value = None
        with pytest.raises(ManagedBrowserError, match="value_readback_refused"):
            instance.read_value("#password")
    assert not instance._proxy.closed


@pytest.mark.parametrize("value", ["x" * 8001, "😀" * 4001, "invalid\ud800"],
                         ids=["overlimit", "surrogate-overlimit", "unpaired-surrogate"])
def test_value_response_boundary_refuses_overlimit_or_invalid_unicode(opened, value):
    instance, _, _, _, _, _, _ = opened
    with patch.object(instance._session, "_find") as find:
        find.return_value.evaluate.return_value = value
        with pytest.raises(ManagedBrowserError, match="value_readback_refused"):
            instance.read_value("#field")
    assert not instance._proxy.closed


def test_text_response_boundary_refuses_prefix_and_accepts_complete_text(opened):
    instance, _, _, _, _, _, _ = opened
    with patch.object(instance._session, "_find") as find:
        find.return_value.evaluate.return_value = "x" * 8001
        with pytest.raises(ManagedBrowserError, match="text_readback_refused"):
            instance.text("#status")
        find.return_value.evaluate.return_value = "complete"
        assert instance.text("#status") == "complete"
    assert not instance._proxy.closed


def test_overlimit_fill_is_refused_before_effect(opened):
    instance, _, _, _, page, _, _ = opened
    with pytest.raises(ManagedBrowserError, match="invalid_action_value"):
        instance.perform(AgentAction("fill", selector="#field", value="😀" * 4001))
    page.locator.assert_not_called()


def test_close_network_before_owned_browser_and_idempotent(opened):
    instance, runtime, browser, _, _, _, _ = opened
    browser.close.side_effect = lambda: instance._proxy.closed or pytest.fail("network still active")
    instance.close()
    assert instance.closed
    instance.close()
    browser.close.assert_called_once()
    runtime.stop.assert_called_once()
    with pytest.raises(ManagedBrowserError, match="retired"):
        instance.observe()


def test_cleanup_error_never_becomes_success_on_second_close(opened):
    instance, _, browser, _, _, _, _ = opened
    browser.close.side_effect = RuntimeError("foreign secret")
    with pytest.raises(ManagedBrowserError, match="cleanup_unconfirmed"):
        instance.close()
    assert not instance.closed
    assert instance._proxy.closed
    with pytest.raises(ManagedBrowserError, match="cleanup_unconfirmed"):
        instance.close()
    assert not instance.closed


def test_setup_failure_closes_owned_context_and_browser():
    runtime = MagicMock()
    browser = runtime.chromium.launch.return_value
    context = browser.new_context.return_value
    context.route_web_socket = None
    factory = MagicMock()
    factory.return_value.start.return_value = runtime
    with patch.object(pw_module, "_require_playwright", return_value=factory):
        with pytest.raises(ManagedBrowserError, match="startup_failed"):
            ManagedBrowserSession.open(BrowserOriginPolicy(("https://allowed.test",)))
    context.close.assert_called_once()
    browser.close.assert_called_once()
    context.new_page.assert_not_called()
    runtime.stop.assert_called_once()


def test_invalid_configuration_is_inert():
    with patch.object(pw_module, "_require_playwright") as runtime:
        with pytest.raises(Exception, match="reviewed origin policy"):
            ManagedBrowserSession.open({"origins": ["https://allowed.test"]})
    runtime.assert_not_called()


def test_guard_rejects_unattributable_request():
    guard = ContextGuard(BrowserOriginPolicy(("https://allowed.test",)), MagicMock())
    route = MagicMock()
    route.request.url = "https://allowed.test"
    type(route.request).frame = property(lambda _self: (_ for _ in ()).throw(RuntimeError("unowned")))
    guard.route(route)
    route.abort.assert_called_once()
    route.continue_.assert_not_called()


def test_failed_network_cleanup_is_unconfirmed_but_still_closes_browser(opened):
    instance, _, browser, _, _, _, _ = opened
    with patch.object(instance._proxy, "close", side_effect=RuntimeError("retirement unknown")):
        with pytest.raises(ManagedBrowserError, match="cleanup_unconfirmed"):
            instance.close()
    assert not instance.closed
    browser.close.assert_called_once()
    instance.close()
    assert instance.closed


def test_observe_is_memory_only_and_retired_constructor_cannot_enter(opened):
    instance, _, _, _, page, _, _ = opened
    with patch.object(instance._session, "observe", return_value={"elements": []}) as observe:
        assert instance.observe(4) == {"elements": []}
        observe.assert_called_once_with(4)
    page.screenshot.assert_not_called()
    inactive = ManagedBrowserSession(BrowserOriginPolicy(("https://allowed.test",)))
    try:
        with pytest.raises(ManagedBrowserError, match="retired"):
            inactive.__enter__()
        assert inactive._proxy.closed
    finally:
        inactive.close()
    assert inactive.closed
