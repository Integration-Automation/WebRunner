"""Active SDK operations and foreign threads cannot certify or consume retirement."""
from concurrent.futures import ThreadPoolExecutor

import pytest

import test_managed_browser as managed_fixtures
import test_managed_browser_readonly as readonly_fixtures
from je_web_runner.utils.agent._managed_guard import ManagedBrowserError
from je_web_runner.utils.agent.types import AgentAction

opened = managed_fixtures.opened
readable = readonly_fixtures.readable


@pytest.mark.parametrize("operation", ["text", "perform", "download"])
def test_active_operation_refuses_freeze_without_retiring_its_owner(readable, operation):
    instance = readable.instance
    refusals = []

    def freeze_during_operation(*_args, **_kwargs):
        with pytest.raises(ManagedBrowserError, match="operation_active") as failure:
            instance.freeze_readonly()
        refusals.append(failure.value.uncertain)
        assert not instance._proxy.closed
        return "first result"

    if operation == "text":
        readable.page.locator("#status").evaluate.side_effect = freeze_during_operation
        assert instance.text("#status") == "first result"
    elif operation == "perform":
        readable.page.locator("#submit").click.side_effect = freeze_during_operation
        instance.perform(AgentAction("click", selector="#submit"))
    else:
        with instance.open_download("https://allowed.test/report"):
            freeze_during_operation()
    assert refusals == [False]
    instance.perform(AgentAction("navigate", value="https://allowed.test/form"))
    assert "navigate" in readable.effects
    assert instance.freeze_readonly().capabilities()["input_supported"] is False


def invoke_operation(target, operation):
    """Invoke real SDK entry points; no fake operation supplies the thread refusal."""
    if operation == "url":
        return target.url
    if operation in {"text", "visible", "read_value", "link"}:
        return getattr(target, operation)("#status")
    if operation == "perform":
        return target.perform(AgentAction("click", selector="#submit"))
    if operation == "upload":
        return target.upload("#file", b"owned", "report.bin")
    if operation == "open_download":
        with target.open_download("https://allowed.test/report"):
            return "unexpected transfer"
    if operation == "set_timeout":
        return target.set_timeout(2)
    return getattr(target, operation)()


@pytest.mark.parametrize("frozen,operation", [
    (False, "freeze_readonly"), (False, "observe"), (False, "text"), (False, "perform"),
    (False, "upload"), (False, "open_download"), (False, "set_timeout"), (False, "close"),
    (False, "__enter__"), (True, "observe"), (True, "text"), (True, "read_value"),
    (True, "visible"), (True, "link"), (True, "url"), (True, "set_timeout"),
    (True, "capabilities"), (True, "close"), (True, "__enter__"),
])
def test_foreign_thread_refuses_before_browser_or_cleanup_access(readable, frozen, operation):
    instance = readable.instance
    target = instance.freeze_readonly() if frozen else instance
    effects = []

    def foreign_browser_access(*_args, **_kwargs):
        effects.append("sdk")
        raise AssertionError("Wrong-thread calls must be refused before touching the foreign SDK")

    readable.page.evaluate.side_effect = foreign_browser_access
    readable.page.locator.side_effect = foreign_browser_access
    readable.browser.close.side_effect = foreign_browser_access
    readable.context.close.side_effect = foreign_browser_access
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(invoke_operation, target, operation)
        with pytest.raises(ManagedBrowserError, match="wrong_thread") as failure:
            future.result(timeout=3)
    assert failure.value.uncertain is False
    assert effects == [] and readable.effects == []
    assert not instance.closed
    assert instance._proxy.closed is frozen
    readable.browser.close.side_effect = None
    readable.context.close.side_effect = None
    instance.close()
    assert instance.closed
