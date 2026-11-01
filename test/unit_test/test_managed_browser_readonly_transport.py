"""Read-only issuance requires real owned transport retirement, without an engine or external host."""
import socket
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

import test_managed_browser as managed_fixtures
import test_managed_browser_readonly as readonly_fixtures
from je_web_runner.utils.agent import scoped_proxy
from je_web_runner.utils.agent.types import AgentError

opened = managed_fixtures.opened
readable = readonly_fixtures.readable


def test_issued_view_has_no_owned_socket_listener_or_new_upstream(readable, monkeypatch):
    instance = readable.instance
    proxy = instance._proxy
    address = urlsplit(proxy.browser_proxy()["server"])
    thread = proxy._thread
    owned, peer = socket.socketpair()
    foreign, foreign_peer = socket.socketpair()
    peer.settimeout(2)
    try:
        proxy.retain_socket(owned)
        peer.sendall(b"before")
        assert owned.recv(6) == b"before"
        view = instance.freeze_readonly()
        assert peer.recv(1) == b""
        assert owned.fileno() == -1 and not thread.is_alive()
        with pytest.raises(OSError):
            with socket.create_connection((address.hostname, address.port), timeout=1):
                pytest.fail("The retired proxy listener must not accept connections")
        foreign_peer.sendall(b"untouched")
        assert foreign.recv(9) == b"untouched"

        def no_connect(*_args):
            pytest.fail("Retirement must refuse before a new upstream connection")

        monkeypatch.setattr(scoped_proxy, "_connect", no_connect)
        with pytest.raises(AgentError, match="not active"):
            proxy.open_upstream("https://allowed.test/resource")
        assert view.text("#status") == "first result"
        assert view.capabilities()["network_retired"] is True
    finally:
        owned.close()
        peer.close()
        foreign.close()
        foreign_peer.close()


def test_registered_route_aborts_approved_requests_after_freeze(readable):
    events = []
    route = SimpleNamespace(
        request=SimpleNamespace(url="https://allowed.test/resource", frame=SimpleNamespace(page=readable.page)),
        continue_=lambda: events.append("forwarded"), abort=lambda reason: events.append(reason))
    callback = readable.context.route.call_args.args[1]
    callback(route)
    assert events == ["forwarded"]
    readable.instance.freeze_readonly()
    callback(route)
    assert events == ["forwarded", "blockedbyclient"]


def test_input_and_routes_are_already_retired_inside_transport_close(readable, monkeypatch):
    instance = readable.instance
    close_transport = instance._proxy.close
    events = []

    def inspect_transition():
        with pytest.raises(AgentError, match="readonly"):
            instance.set_timeout(2)
        route = SimpleNamespace(
            request=SimpleNamespace(url="https://allowed.test/resource"),
            continue_=lambda: events.append("forwarded"), abort=lambda reason: events.append(reason))
        readable.context.route.call_args.args[1](route)
        assert events == ["blockedbyclient"]
        close_transport()

    monkeypatch.setattr(instance._proxy, "close", inspect_transition)
    view = instance.freeze_readonly()
    monkeypatch.setattr(instance._proxy, "close", close_transport)
    assert view.capabilities()["input_supported"] is False
