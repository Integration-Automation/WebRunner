"""Only the allowlisted builtins are dispatchable from an action list (workspace item X-12).

The executor used to register every builtin function except a blocklist, which left `dir`,
`hasattr`, `id`, `isinstance`, `issubclass`, `iter` and `next` callable from an action JSON file and
would have handed action lists whatever builtin a future Python adds.
"""
import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException
from je_web_runner.utils.executor.action_executor import SAFE_BUILTINS, Executor


@pytest.fixture()
def executor():
    return Executor()


def test_registered_builtins_are_exactly_the_allowlist(executor):
    registered = {name for name in executor.event_dict if not name.startswith("WR_")}
    assert registered == set(SAFE_BUILTINS)  # nosec B101


@pytest.mark.parametrize("name", [
    "eval", "exec", "compile", "__import__", "__build_class__", "open", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
    "dir", "hasattr", "id", "isinstance", "issubclass", "iter", "next",
])
def test_unsafe_or_unlisted_builtin_is_not_registered(executor, name):
    assert name not in executor.event_dict  # nosec B101


def test_every_allowlisted_builtin_is_callable(executor):
    for name in SAFE_BUILTINS:
        assert callable(executor.event_dict[name])  # nosec B101


def test_an_allowlisted_builtin_still_runs(executor):
    result = executor.execute_action([["len", [[1, 2, 3]]]])
    assert any(value == 3 for value in result.values())  # nosec B101


def test_dispatching_a_blocked_builtin_raises(executor):
    with pytest.raises(WebRunnerExecuteException):
        executor._execute_event(["eval", ["1 + 1"]])
