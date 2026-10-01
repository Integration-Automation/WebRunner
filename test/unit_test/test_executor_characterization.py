"""
What the action executor does, pinned before it moves onto je_action_core.

Covers what the other executor tests leave open: the printed records, the exact error texts, the order of the
refusal and the lookup, the list rules, ``add_command_to_executor``, ``execute_files``, retries of an unknown
command, and the log lines.
"""
import json
import logging
from collections import OrderedDict

import pytest

from je_web_runner.utils.exception.exceptions import WebRunnerAddCommandException, WebRunnerExecuteException
from je_web_runner.utils.executor import action_executor
from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.logging.loggin_instance import web_runner_logger

_LIST_ERROR = "executor received invalid data: list is empty or of wrong type"


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append((record.levelname, record.getMessage()))


@pytest.fixture()
def log_lines():
    handler = _Collect()
    previous = web_runner_logger.level
    web_runner_logger.addHandler(handler)
    web_runner_logger.setLevel(logging.DEBUG)
    try:
        yield handler.lines
    finally:
        web_runner_logger.removeHandler(handler)
        web_runner_logger.setLevel(previous)


@pytest.fixture()
def runner():
    executor = Executor()
    executor.event_dict["WR_t_add"] = lambda a, b=0: a + b
    executor.event_dict["WR_t_boom"] = _boom
    return executor


def _boom():
    raise RuntimeError("boom")


def test_execute_action_prints_each_key_then_value_and_returns_the_records(runner, capsys):
    records = runner.execute_action([["WR_t_add", [1, 2]], ["WR_t_add", {"a": 5}], ["WR_t_boom"]])
    assert records == {
        "execute: ['WR_t_add', [1, 2]]": 3,
        "execute: ['WR_t_add', {'a': 5}]": 5,
        "execute: ['WR_t_boom']": "RuntimeError('boom')",
    }
    assert capsys.readouterr().out == (
        "execute: ['WR_t_add', [1, 2]]\n3\n"
        "execute: ['WR_t_add', {'a': 5}]\n5\n"
        "execute: ['WR_t_boom']\nRuntimeError('boom')\n"
    )


def test_collect_action_results_prints_nothing(runner, capsys):
    records, failed = runner.collect_action_results([["WR_t_boom"], ["WR_t_add", [1], {"b": 4}]])
    assert records == {"execute: ['WR_t_boom']": "RuntimeError('boom')", "execute: ['WR_t_add', [1], {'b': 4}]": 5}
    assert failed == ["execute: ['WR_t_boom']"]
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(("action", "message"), [
    (["WR_nope"], "executor received invalid data unknown command: WR_nope"),
    (["WR_t_add", {"a": 1}, {"b": 2}],
     "executor received invalid data: 3-element action requires [cmd, [positional], {kwargs}]"),
    (["WR_t_add", [1], [2]],
     "executor received invalid data: 3-element action requires [cmd, [positional], {kwargs}]"),
    (["WR_t_add", [1], {"b": 1}, "extra"], "executor received invalid data ['WR_t_add', [1], {'b': 1}, 'extra']"),
])
def test_a_bad_action_is_recorded_with_its_message(runner, action, message):
    with pytest.raises(WebRunnerExecuteException) as raised:
        runner._execute_event(action)
    assert str(raised.value) == message
    records, failed = runner.collect_action_results([action])
    assert records == {f"execute: {action}": f"WebRunnerExecuteException({message!r})"}
    assert failed == [f"execute: {action}"]


def test_a_tuple_payload_is_positional_in_a_three_element_action(runner):
    assert runner._execute_event(["WR_t_add", (1,), {"b": 2}]) == 3


def test_an_empty_action_raises_index_error(runner):
    with pytest.raises(IndexError):
        runner._execute_event([])


def test_a_refused_command_is_refused_before_it_is_looked_up(runner):
    with runner.restricted(["WR_nope"]):
        with pytest.raises(WebRunnerExecuteException) as raised:
            runner._execute_event(["WR_nope"])
    assert str(raised.value) == "command 'WR_nope' is not allowed here"


def test_a_closed_script_gate_is_checked_before_the_lookup(runner):
    runner.event_dict.pop("WR_execute_script", None)
    runner.set_allow_arbitrary_script(False)
    with pytest.raises(WebRunnerExecuteException) as raised:
        runner._execute_event(["WR_execute_script", ["return 1"]])
    assert "arbitrary-script command 'WR_execute_script' is disabled" in str(raised.value)


def test_an_empty_list_runs_nothing_and_prints_nothing(runner, capsys):
    assert runner.execute_action([]) == {}
    assert runner.collect_action_results({"webdriver_wrapper": []}) == ({}, [])
    assert capsys.readouterr().out == ""


def test_a_document_keeps_its_list_under_webdriver_wrapper(runner):
    assert runner.execute_action({"webdriver_wrapper": [["WR_t_add", [2]]]}) == {"execute: ['WR_t_add', [2]]": 2}


@pytest.mark.parametrize("action_list", [
    {"other": [["WR_t_add", [1]]]},
    {"webdriver_wrapper": "WR_quit"},
    OrderedDict(webdriver_wrapper=[["WR_t_add", [1]]]),
    "WR_quit",
    None,
    (["WR_t_add", [1]],),
])
def test_anything_else_raises_the_list_error_and_logs_it(runner, action_list, log_lines):
    with pytest.raises(WebRunnerExecuteException) as raised:
        runner.execute_action(action_list)
    assert str(raised.value) == _LIST_ERROR
    # A plain dict logs what it holds under the key (None when it has none), anything else logs itself.
    found = action_list.get("webdriver_wrapper") if type(action_list) is dict else action_list
    assert ("ERROR", f"execute_action, action_list: {found}, failed: {_LIST_ERROR}") in log_lines


def test_the_list_is_logged_first_and_each_failure_names_its_action(runner, log_lines):
    runner.collect_action_results([["WR_t_add", [1]], ["WR_t_boom"]])
    assert log_lines[0] == ("INFO", "execute_action, action_list: [['WR_t_add', [1]], ['WR_t_boom']]")
    failures = [message for level, message in log_lines if level == "ERROR"]
    assert len(failures) == 1
    assert "action: ['WR_t_boom']" in failures[0]
    assert failures[0].endswith("failed: RuntimeError('boom')")


def test_execute_files_logs_the_paths_and_runs_each_file(runner, tmp_path, log_lines, capsys):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text(json.dumps([["WR_t_add", [1, 1]]]), encoding="utf-8")
    second.write_text(json.dumps({"webdriver_wrapper": [["WR_t_add", [3]]]}), encoding="utf-8")
    paths = [str(first), str(second)]
    assert runner.execute_files(paths) == [{"execute: ['WR_t_add', [1, 1]]": 2}, {"execute: ['WR_t_add', [3]]": 3}]
    assert ("INFO", f"execute_files, execute_files_list: {paths}") in log_lines
    assert "execute: ['WR_t_add', [1, 1]]\n2\n" in capsys.readouterr().out


def test_an_unknown_command_is_retried_like_any_failure(runner, log_lines, monkeypatch):
    monkeypatch.setattr(action_executor.time, "sleep", lambda _seconds: None)
    runner.set_retry_policy(retries=2, backoff=0.0)
    records, failed = runner.collect_action_results([["WR_nope"]])
    assert failed == ["execute: ['WR_nope']"]
    retries = [message for level, message in log_lines if level == "WARNING"]
    assert len(retries) == 2
    assert retries[0].startswith("action ['WR_nope'] failed on attempt 1, retrying: ")


def test_add_command_takes_functions_and_methods_and_stops_at_the_first_other(monkeypatch):
    fresh = Executor()
    monkeypatch.setattr(action_executor, "executor", fresh)

    class Holder:
        def method(self):
            return "method"

    action_executor.add_command_to_executor({"WR_t_fn": _boom, "WR_t_method": Holder().method})
    assert fresh.event_dict["WR_t_fn"] is _boom
    for refused in (len, Holder, "not callable"):
        with pytest.raises(WebRunnerAddCommandException) as raised:
            action_executor.add_command_to_executor({"WR_t_ok": _boom, "WR_t_bad": refused})
        assert str(raised.value) == "command value type must be a method or function"
        assert "WR_t_ok" in fresh.event_dict
        assert "WR_t_bad" not in fresh.event_dict


def test_the_executor_registers_the_safe_builtins_only():
    commands = Executor().event_dict
    assert commands["len"] is len
    for name in ("eval", "exec", "open", "__import__", "getattr", "compile"):
        assert name not in commands
