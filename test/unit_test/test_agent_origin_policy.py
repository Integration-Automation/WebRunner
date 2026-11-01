"""Origin grants are immutable and exact across schemes, authorities and browser URL normalization."""
import pytest

from je_web_runner.utils.agent import AgentError


def test_policy_canonicalizes_only_equivalent_ascii_origins():
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    policy = BrowserOriginPolicy(("https://EXAMPLE.test:443", "https://example.test/", "http://[::1]:80"))
    assert policy.origins == ("http://[::1]", "https://example.test")
    assert policy.allows("https://example.test/path?name=value")
    assert not policy.allows("http://example.test/path")
    assert not policy.allows("https://other.example.test/")
    assert not policy.allows("https://example.test:444/")


@pytest.mark.parametrize("origin", [
    "file:///secret", "http://user:secret@example.test", "https://@example.test", "https://example.test/private",
    "https://example.test?token=hidden", "https://example.test#fragment", "http://example.test:99999",
    "https://faß.test", "http://127.1", "http://0177.0.0.1", "http://2130706433", "http://example.test:0",
    "https://exam\nple.test", "https://example.test\\@other.test", "http://[::1%25zone]", "",
])
def test_origin_configuration_rejects_ambiguous_or_widened_grants(origin):
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    with pytest.raises(AgentError):
        BrowserOriginPolicy((origin,))


def test_unknown_policy_fields_and_mutation_are_rejected():
    from je_web_runner.utils.agent.network_policy import BrowserOriginPolicy
    from dataclasses import FrozenInstanceError
    source = ["https://example.test"]
    policy = BrowserOriginPolicy(source)
    source.append("https://other.test")
    assert policy.origins == ("https://example.test",)
    with pytest.raises(FrozenInstanceError):
        policy.origins = ("https://other.test",)
    with pytest.raises(AgentError):
        BrowserOriginPolicy.from_dict({"origins": ["https://example.test"], "executable": "browser.exe"})
    with pytest.raises(AgentError):
        BrowserOriginPolicy(())
