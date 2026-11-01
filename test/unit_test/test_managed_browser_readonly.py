"""Permanent same-context SDK reads with a fake engine and real owned transport."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import test_managed_browser as managed_fixtures
from je_web_runner.utils.agent import managed_browser as module
from je_web_runner.utils.agent._managed_guard import ManagedBrowserError
from je_web_runner.utils.agent.types import AgentAction
from je_web_runner.webdriver import playwright_wrapper as pw_module

opened = managed_fixtures.opened


@pytest.fixture
def readable(opened, monkeypatch):
    """Give the foreign fake page mutable app state; later engine startup is forbidden."""
    instance, runtime, browser, context, page, events, page_events = opened
    page.url = "https://allowed.test/form"
    values = {"#status": "first result", "#field": "original value", "#report": "https://allowed.test/report"}
    effects = []
    elements = {}

    def locator(selector):
        if selector not in elements:
            element = MagicMock()
            element.count.return_value = 1
            element.nth.return_value = element
            element.is_visible.return_value = True
            element.is_enabled.return_value = True
            element.evaluate.side_effect = lambda _script: values.get(selector, "unused")
            element.click.side_effect = lambda **_kwargs: effects.append("click")
            element.set_input_files.side_effect = lambda *_args, **_kwargs: effects.append("upload")
            elements[selector] = element
        return elements[selector]

    def snapshot(_script):
        return {"url": page.url, "title": "Original page", "elements": [], "text": values["#status"],
                "frames": [], "console_errors": [], "network_errors": []}

    def no_new_browser(*_args, **_kwargs):
        raise AssertionError("Completion retirement must preserve the original browser context")

    @contextmanager
    def controlled_download(*_args, **_kwargs):
        effects.append("download")
        yield SimpleNamespace(read=lambda: b"")

    page.locator.side_effect = locator
    # A Playwright Page has no Selenium execute_script; MagicMock otherwise invents it.
    del page.execute_script
    page.evaluate.side_effect = snapshot
    page.goto.side_effect = lambda *_args, **_kwargs: effects.append("navigate")
    context.new_page.side_effect = no_new_browser
    browser.new_context.side_effect = no_new_browser
    runtime.chromium.launch.side_effect = no_new_browser
    monkeypatch.setattr(pw_module, "_require_playwright", no_new_browser)
    monkeypatch.setattr(module, "download_response", controlled_download)
    return SimpleNamespace(instance=instance, runtime=runtime, browser=browser, context=context, page=page,
                           events=events, page_events=page_events, values=values, effects=effects)


def test_freeze_preserves_original_context_and_live_capabilities(readable):
    instance = readable.instance
    original = instance._session
    view = instance.freeze_readonly()
    assert instance._proxy.closed
    assert instance._session is original
    assert original.driver is readable.page
    assert not instance.closed
    assert view.policy is instance.policy
    assert view.context_id == instance.context_id
    assert view.capabilities() == {"contract": 1, "input_supported": False,
                                   "network_retired": True, "context_id": instance.context_id}
    assert readable.effects == []


def test_frozen_dom_reads_are_fresh_from_the_retained_page(readable):
    view = readable.instance.freeze_readonly()
    assert view.url == "https://allowed.test/form"
    assert view.text("#status") == "first result"
    assert view.read_value("#field") == "original value"
    assert view.visible("#status") is True
    assert view.link("#report") == "https://allowed.test/report"
    readable.values.update({"#status": "independent current result", "#field": "new value"})
    assert view.text("#status") == "independent current result"
    assert view.read_value("#field") == "new value"
    observed = view.observe(7)
    assert observed["text"] == "independent current result"
    assert observed["step"] == 7


def test_frozen_timeout_only_bounds_reads_without_input(readable):
    original = readable.instance._session
    view = readable.instance.freeze_readonly()
    view.set_timeout(2)
    assert original.timeout == 2
    assert readable.effects == []


@pytest.mark.parametrize("operation", ["perform", "upload", "open_download", "set_timeout"])
def test_original_reference_cannot_mutate_after_readonly_retirement(readable, operation):
    instance = readable.instance
    view = instance.freeze_readonly()
    with pytest.raises(ManagedBrowserError, match="readonly") as failure:
        if operation == "perform":
            instance.perform(AgentAction("click", selector="#submit"))
        elif operation == "upload":
            instance.upload("#file", b"owned bytes", "report.bin")
        elif operation == "open_download":
            with instance.open_download("https://allowed.test/report"):
                pytest.fail("No transfer context may be issued after input retirement")
        else:
            instance.set_timeout(60)
    assert failure.value.uncertain is False
    assert readable.effects == []
    assert view.text("#status") == "first result"


def test_repeat_freeze_keeps_one_context_until_explicit_close(readable):
    instance = readable.instance
    view = instance.freeze_readonly()
    assert instance.freeze_readonly() is view
    context_id = view.context_id
    view.close()
    assert instance.closed and instance._proxy.closed
    assert view.context_id == context_id
    instance.close()
    view.close()
    with pytest.raises(ManagedBrowserError, match="retired"):
        view.observe()
    with pytest.raises(ManagedBrowserError, match="retired"):
        view.capabilities()
