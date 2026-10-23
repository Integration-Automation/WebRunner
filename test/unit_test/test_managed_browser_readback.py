"""Execute fixed readback JavaScript in installed Node; no browser, DOM or network is launched."""
import json
import shutil
import subprocess

import pytest

from je_web_runner.utils.agent import managed_browser as module


def read_script(kind, **values):
    executable = shutil.which("node")
    if executable is None:
        pytest.skip("fixed JavaScript contract requires an explicitly installed Node runtime")
    script = getattr(module, "_READ_" + kind.upper())
    program = """
      const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
      const element = {...input,
        getAttribute: name => name === 'type' ? input.type : null,
        closest: () => input.secret ? {} : null,
        querySelector: () => input.secretChild ? {} : null};
      const read = (SCRIPT);
      process.stdout.write(JSON.stringify(read(element)));
    """.replace("SCRIPT", script)
    payload = {"tagName": "INPUT", "type": "text", "autocomplete": "", "value": "", "innerText": "",
               "secret": False, "secretChild": False, **values}
    result = subprocess.run([executable, "-e", program], input=json.dumps(payload), capture_output=True,
                            text=True, encoding="utf-8", timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("kind,field", [("value", "value"), ("text", "innerText")])
def test_overlong_readback_is_refused_instead_of_returning_matching_prefix(kind, field):
    result = read_script(kind, **{field: "x" * 8000 + "changed suffix"})
    assert result is None


@pytest.mark.parametrize("kind,field", [("value", "value"), ("text", "innerText")])
@pytest.mark.parametrize("value", ["", "exact", "x" * 8000, "😀" * 4000],
                         ids=["empty", "short", "limit", "surrogate-limit"])
def test_complete_bounded_readback_keeps_every_character(kind, field, value):
    assert read_script(kind, **{field: value}) == value


@pytest.mark.parametrize("kind,field", [("value", "value"), ("text", "innerText")])
def test_utf16_limit_never_splits_surrogate_pair(kind, field):
    assert read_script(kind, **{field: "😀" * 4001}) is None


@pytest.mark.parametrize("changes", [
    {"type": "password"}, {"type": "file"}, {"type": "hidden"}, {"secret": True},
    {"autocomplete": "current-password"}, {"autocomplete": "new-password"}, {"tagName": "DIV"},
])
def test_value_readback_refuses_unsupported_or_sensitive_controls(changes):
    assert read_script("value", value="private", **changes) is None


@pytest.mark.parametrize("changes", [{"secret": True}, {"secretChild": True}])
def test_text_readback_refuses_marked_secret_ancestor_or_descendant(changes):
    assert read_script("text", innerText="private", **changes) is None


def test_managed_sdk_publishes_exact_readback_contract_version_without_launch():
    assert module.ManagedBrowserSession.contract_version == 1
