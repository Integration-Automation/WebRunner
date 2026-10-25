"""Retirement and context-loss refusals cannot turn historical metadata into live authority."""
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

import test_managed_browser as managed_fixtures
import test_managed_browser_readonly as readonly_fixtures
from je_web_runner.utils.agent._managed_guard import ManagedBrowserError
from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.agent.types import AgentAction

opened = managed_fixtures.opened
readable = readonly_fixtures.readable


def test_failed_retirement_cannot_issue_a_reader_or_revive_input(readable, monkeypatch):
    instance = readable.instance
    close_transport = instance._proxy.close

    def unconfirmed():
        close_transport()
        raise RuntimeError("PRIVATE_INPUT")

    monkeypatch.setattr(instance._proxy, "close", unconfirmed)
    with pytest.raises(ManagedBrowserError, match="retirement_unconfirmed") as failure:
        instance.freeze_readonly()
    assert failure.value.uncertain is True
    assert "PRIVATE_INPUT" not in str(failure.value)
    assert failure.value.__suppress_context__
    assert not instance.closed
    with pytest.raises(ManagedBrowserError):
        instance.perform(AgentAction("click", selector="#submit"))
    with pytest.raises(ManagedBrowserError):
        instance.freeze_readonly()
    monkeypatch.setattr(instance._proxy, "close", close_transport)
    for _index in range(2):
        with pytest.raises(ManagedBrowserError, match="cleanup_unconfirmed"):
            instance.close()
        assert not instance.closed
    assert readable.effects == []


@pytest.mark.parametrize("damage", ["session", "page", "origin", "same-origin-document"])
def test_lost_context_stays_unusable_after_apparent_restoration(readable, damage):
    instance = readable.instance
    view = instance.freeze_readonly()
    original_session, original_page, original_url = instance._session, instance._guard.page, readable.page.url
    replacement = MagicMock()
    replacement.url = "https://allowed.test/form"
    if damage == "session":
        instance._session = BrowserSession(replacement, "playwright")
    elif damage == "page":
        instance._guard.page = replacement
    elif damage == "origin":
        readable.page.url = "https://not-reviewed.test/private?token=PRIVATE_INPUT"
    else:
        readable.page.url = "https://allowed.test/another-document"
    with pytest.raises(ManagedBrowserError, match="readonly_context") as failure:
        view.text("#status")
    assert "PRIVATE_INPUT" not in str(failure.value)
    instance._session, instance._guard.page, readable.page.url = original_session, original_page, original_url
    with pytest.raises(ManagedBrowserError):
        view.capabilities()
    with pytest.raises(ManagedBrowserError):
        view.text("#status")


@pytest.mark.parametrize("url", ["https://allowed.test/another-document", "https://unreviewed.test/private"])
def test_navigation_during_transport_retirement_does_not_issue_a_view(readable, monkeypatch, url):
    instance = readable.instance
    close_transport = instance._proxy.close

    def changed_context():
        close_transport()
        readable.page.url = url

    monkeypatch.setattr(instance._proxy, "close", changed_context)
    with pytest.raises(ManagedBrowserError, match="readonly_retirement_unconfirmed") as failure:
        instance.freeze_readonly()
    assert failure.value.uncertain is True
    assert "unreviewed" not in str(failure.value)
    monkeypatch.setattr(instance._proxy, "close", close_transport)
    with pytest.raises(ManagedBrowserError):
        instance.freeze_readonly()


def test_url_change_during_a_read_does_not_publish_an_apparently_matching_result(readable):
    view = readable.instance.freeze_readonly()
    element = readable.page.locator("#status")

    def changed(_script):
        readable.page.url = "https://allowed.test/another-document"
        return "apparently complete"

    element.evaluate.side_effect = changed
    with pytest.raises(ManagedBrowserError, match="readonly_context"):
        view.text("#status")
    readable.page.url = "https://allowed.test/form"
    with pytest.raises(ManagedBrowserError):
        view.observe()


@pytest.mark.parametrize("event,reason", [
    ("dialog", "human_review_required"), ("download", "download_blocked"),
    ("filechooser", "upload_blocked"), ("crash", "page_crashed"), ("close", "page_closed"),
])
def test_readonly_view_retains_sticky_unexpected_ui_refusals(readable, event, reason):
    view = readable.instance.freeze_readonly()
    for callback in readable.page_events[event]:
        callback(MagicMock())
    with pytest.raises(ManagedBrowserError) as failure:
        view.text("#status")
    assert failure.value.reason == reason
    assert readable.instance._proxy.closed
    with pytest.raises(ManagedBrowserError):
        readable.instance.perform(AgentAction("click", selector="#submit"))
    assert readable.effects == []


@pytest.mark.parametrize("value", [None, "x" * 8001, "\ud800"], ids=["secret-refused", "over-limit", "invalid-unicode"])
def test_readonly_value_keeps_complete_masked_readback_contract(readable, value):
    view = readable.instance.freeze_readonly()
    readable.values["#field"] = value
    with pytest.raises(ManagedBrowserError, match="value_readback_refused"):
        view.read_value("#field")
    assert view.text("#status") == "first result"


def test_capability_dict_changes_do_not_change_actual_reader_authority(readable):
    view = readable.instance.freeze_readonly()
    description = view.capabilities()
    description.update(input_supported=True, network_retired=False, context_id="forged")
    assert view.capabilities() == {"contract": 1, "input_supported": False,
                                   "network_retired": True, "context_id": readable.instance.context_id}
    with pytest.raises(ManagedBrowserError, match="readonly_operation"):
        view._invoke("perform", (AgentAction("click", selector="#submit"),))
    assert readable.effects == []


def test_reader_context_manager_closes_only_its_existing_owner(readable):
    view = readable.instance.freeze_readonly()
    with pytest.raises(ValueError, match="client failure"):
        with view as active:
            assert active.text("#status") == "first result"
            raise ValueError("client failure")
    assert readable.instance.closed
    with pytest.raises(ManagedBrowserError, match="retired"):
        view.__enter__()


def test_same_url_document_navigation_invalidates_frozen_context(readable):
    view = readable.instance.freeze_readonly()
    for callback in readable.page_events.get("framenavigated", []):
        callback(MagicMock())
    with pytest.raises(ManagedBrowserError, match="readonly_context_changed"):
        view.text("#status")
    with pytest.raises(ManagedBrowserError):
        view.capabilities()


def test_close_does_not_retire_another_owned_context(readable):
    first = readable.instance.freeze_readonly()
    with contextmanager(managed_fixtures.opened.__wrapped__)() as second_fixture:
        second, _, _, _, page, _, _ = second_fixture
        page.url = "https://allowed.test/form"
        other = second.freeze_readonly()
        assert first.context_id != other.context_id
        first.close()
        assert not second.closed
        assert other.capabilities()["input_supported"] is False
        assert other.url == "https://allowed.test/form"
    assert second.closed and readable.instance.closed


@pytest.mark.parametrize("url", ["about:blank", "https://unreviewed.test/private"])
def test_unreviewed_preflight_does_not_retire_a_writable_owner(readable, url):
    instance = readable.instance
    readable.page.url = url
    with pytest.raises(ManagedBrowserError, match="readonly_context_unavailable") as failure:
        instance.freeze_readonly()
    assert failure.value.uncertain is False and not instance._proxy.closed
    readable.page.url = "https://allowed.test/form"
    instance.perform(AgentAction("navigate", value="https://allowed.test/form"))
    assert readable.effects == ["navigate"]
    assert instance.freeze_readonly().url == "https://allowed.test/form"
