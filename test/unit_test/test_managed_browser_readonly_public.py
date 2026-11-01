"""Public imports must yield the actual issued view, with no startup on construction."""
from importlib import import_module

import pytest

import test_managed_browser as managed_fixtures
import test_managed_browser_readonly as readonly_fixtures
from je_web_runner.utils.agent.managed_browser import ManagedBrowserSession
from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
from je_web_runner.utils.agent.scoped_proxy import ScopedBrowserProxy
from je_web_runner.utils.agent._managed_guard import ManagedBrowserError
from je_web_runner.webdriver import playwright_wrapper as pw_module

opened = managed_fixtures.opened
readable = readonly_fixtures.readable


@pytest.mark.parametrize("facade", ["je_web_runner", "je_web_runner.api.ai", "je_web_runner.utils.agent"])
def test_public_sdk_view_type_is_the_actual_issued_reader(readable, facade):
    view = readable.instance.freeze_readonly()
    public_type = getattr(import_module(facade), "ManagedReadOnlySession", None)
    assert public_type is type(view)
    assert isinstance(view, public_type)
    assert type(ManagedBrowserSession.readonly_contract_version) is int
    assert ManagedBrowserSession.readonly_contract_version == 1
    assert view.capabilities()["input_supported"] is False
    assert not any(hasattr(view, name) for name in ("perform", "upload", "open_download", "driver", "page"))


def test_unopened_owner_cannot_create_a_reader_or_start_transport(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("SDK construction and refused preflight must not start a browser or proxy")

    monkeypatch.setattr(ScopedBrowserProxy, "start", forbidden)
    monkeypatch.setattr(pw_module, "_require_playwright", forbidden)
    instance = ManagedBrowserSession(BrowserOriginPolicy(("https://allowed.test",)))
    with pytest.raises(ManagedBrowserError, match="retired"):
        instance.freeze_readonly()
    assert not instance.closed
    instance.close()
    assert instance.closed
