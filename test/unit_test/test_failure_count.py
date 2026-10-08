"""The CLI's exit status: a run in which an action or a file failed returns 1."""
import json

import pytest

from je_web_runner.utils.cli import cli_main
from je_web_runner.utils.cli.failure_count import FailureCount, note_failed_file
from je_web_runner.utils.executor.action_executor import execute_action, executor

# No command has this name, so binding the action raises.
RAISES = ["WR_no_such_command"]
PASSES = ["print", ["failure-count-test"]]


def _write(path, actions) -> str:
    path.write_text(json.dumps(actions), encoding="utf-8")
    return str(path)


def test_an_action_that_raises_is_counted():
    with FailureCount() as count:
        execute_action([RAISES, PASSES, RAISES])
    assert count.failed == 2


def test_nothing_failed_is_zero():
    with FailureCount() as count:
        execute_action([PASSES])
    assert count.failed == 0


def test_a_file_reported_as_failed_is_counted():
    with FailureCount() as count:
        note_failed_file()
    assert count.failed == 1


def test_a_failed_file_outside_a_count_is_ignored():
    note_failed_file()
    with FailureCount() as count:
        pass
    assert count.failed == 0


def test_the_executor_gets_its_reporter_back():
    reporter = executor.settings.reporter
    with FailureCount():
        assert executor.settings.reporter is not reporter
    assert executor.settings.reporter is reporter


def test_the_reporter_comes_back_when_the_block_raises():
    reporter = executor.settings.reporter
    with pytest.raises(RuntimeError), FailureCount():
        raise RuntimeError("stopped")
    assert executor.settings.reporter is reporter


def test_main_returns_1_when_an_action_failed(tmp_path, capsys):
    assert cli_main.main(["-e", _write(tmp_path / "bad.json", [RAISES, PASSES])]) == 1
    captured = capsys.readouterr()
    assert "error: 1 action(s) or file(s) failed" in captured.err
    assert "failure-count-test" in captured.out


def test_main_returns_0_when_every_action_passed(tmp_path):
    assert cli_main.main(["-e", _write(tmp_path / "ok.json", [PASSES])]) == 0


def test_main_counts_every_file_of_a_directory(tmp_path, capsys):
    _write(tmp_path / "a_ok.json", [PASSES])
    _write(tmp_path / "b_bad.json", [RAISES])
    _write(tmp_path / "c_bad.json", [RAISES])
    assert cli_main.main(["-d", str(tmp_path)]) == 1
    assert "error: 2 action(s) or file(s) failed" in capsys.readouterr().err


def test_a_file_that_failed_in_another_process_fails_the_run(tmp_path, monkeypatch):
    # The process pool is replaced: what matters is that a file reported as not passed is counted.
    class _Pool:
        def __init__(self, max_workers):
            self.max_workers = max_workers

        def __enter__(self):
            return self

        def __exit__(self, *_details):
            return False

        @staticmethod
        def map(_function, files):
            return [(path, False, []) for path in files]

    monkeypatch.setattr(cli_main, "ProcessPoolExecutor", _Pool)
    _write(tmp_path / "a.json", [PASSES])
    _write(tmp_path / "b.json", [PASSES])
    assert cli_main.main(["-d", str(tmp_path), "--parallel", "2", "--parallel-mode", "process"]) == 1
