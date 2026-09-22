"""Five text scanners that used super-linear regexes (SonarCloud python:S8786).

Each case pins the behaviour the old pattern had on ordinary input, then feeds an adversarial input
that made the old pattern backtrack quadratically and checks it now finishes quickly.
"""
import time

import pytest

from je_web_runner.utils.hydration_check.check import _normalise_html
from je_web_runner.utils.locator_hardener.hardener import _is_deeply_nested
from je_web_runner.utils.story_to_actions.generator import _fenced_block
from je_web_runner.utils.test_debt_dashboard.debt import _TODO_RE
from je_web_runner.utils.test_owners_map.owners import parse_codeowners

_BIG = 200_000
_BUDGET_SECONDS = 1.0


def _fast(call):
    start = time.perf_counter()
    result = call()
    assert time.perf_counter() - start < _BUDGET_SECONDS  # nosec B101
    return result


@pytest.mark.parametrize("html, expected", [
    ("<div>  <span> hi </span>  </div>", "<div><span>hi</span></div>"),
    ('<div data-reactroot="" class="x">  </div>', '<div class="x"></div>'),
    ("  <p>a</p>  b  ", "<p>a</p>b"),
    ("a   b", "a b"),
])
def test_normalise_html_strips_whitespace_around_tags(html, expected):
    assert _normalise_html(html) == expected  # nosec B101


def test_normalise_html_is_linear_on_long_whitespace():
    assert _fast(lambda: _normalise_html("a" + " " * _BIG + "b")) == "a b"  # nosec B101


@pytest.mark.parametrize("selector, deep", [
    ("a b c d", True),
    (" b c d", True),
    ("a b c", False),
    ("div > span", False),
    ("", False),
    ("#main .list li a", True),
])
def test_deeply_nested_selectors(selector, deep):
    assert _is_deeply_nested(selector) is deep  # nosec B101


def test_deeply_nested_is_linear():
    assert _fast(lambda: _is_deeply_nested(" " * _BIG + "a")) is False  # nosec B101


@pytest.mark.parametrize("reply, body", [
    ('```json\n[{"a": 1}]\n```', '[{"a": 1}]'),
    ('Here you go:\n```\n[1]\n``` thanks', "[1]"),
    ("[1, 2]", "[1, 2]"),
    ("```json\n[1]", "```json\n[1]"),  # unclosed fence: the text is returned as it was
])
def test_fenced_block(reply, body):
    assert _fenced_block(reply) == body  # nosec B101


def test_fenced_block_is_linear_on_an_unclosed_fence():
    reply = "```" + "x" * _BIG
    assert _fast(lambda: _fenced_block(reply)) == reply  # nosec B101


@pytest.mark.parametrize("line, tag, reason", [
    ("x = 1  # TODO: tidy up", "TODO", "tidy up"),
    ("# fixme   handle None", "fixme", "handle None"),
    ("#TODO", "TODO", ""),
])
def test_todo_marker(line, tag, reason):
    match = _TODO_RE.search(line)
    assert match.group(1) == tag  # nosec B101
    assert match.group(2).lstrip(": \t").strip() == reason  # nosec B101


def test_todo_marker_is_linear_on_long_separators():
    line = "# TODO" + ": " * _BIG + "x"
    assert _fast(lambda: _TODO_RE.search(line)) is not None  # nosec B101


def test_codeowners_trailing_comments():
    rules = parse_codeowners("/docs/  @docs#1   # the docs team\n# whole-line comment\n*.py @py\n").rules
    assert [(rule.pattern, rule.owners) for rule in rules] == [  # nosec B101
        ("/docs/", ["@docs#1"]), ("*.py", ["@py"])]


def test_codeowners_is_linear_on_long_whitespace():
    text = "*.py @py" + " " * _BIG + "x\n"
    assert len(_fast(lambda: parse_codeowners(text)).rules) == 1  # nosec B101
