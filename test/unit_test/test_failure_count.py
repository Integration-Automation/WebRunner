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
    assert count.failed == 2  # nosec B101


def test_nothing_failed_is_zero():
    with FailureCount() as count:
        execute_action([PASSES])
    assert count.failed == 0  # nosec B101


def test_a_file_reported_as_failed_is_counted():
    with FailureCount() as count:
        note_failed_file()
    assert count.failed == 1  # nosec B101


def test_a_failed_file_outside_a_count_is_ignored():
    note_failed_file()
    with FailureCount() as count:
        pass
    assert count.failed == 0  # nosec B101


def test_the_executor_gets_its_reporter_back():
    reporter = executor.settings.reporter
    with FailureCount():
        assert executor.settings.reporter is not reporter  # nosec B101
    assert executor.settings.reporter is reporter  # nosec B101


def test_the_reporter_comes_back_when_the_block_raises():
    reporter = executor.settings.reporter
    with pytest.raises(RuntimeError), FailureCount():
        raise RuntimeError("stopped")
    assert executor.settings.reporter is reporter  # nosec B101


def test_main_returns_1_when_an_action_failed(tmp_path, capsys):
    assert cli_main.main(["-e", _write(tmp_path / "bad.json", [RAISES, PASSES])]) == 1  # nosec B101
    captured = capsys.readouterr()
    assert "error: 1 action(s) or file(s) failed" in captured.err  # nosec B101
    assert "failure-count-test" in captured.out  # nosec B101


def test_main_returns_0_when_every_action_passed(tmp_path):
    assert cli_main.main(["-e", _write(tmp_path / "ok.json", [PASSES])]) == 0  # nosec B101


def test_main_counts_every_file_of_a_directory(tmp_path, capsys):
    _write(tmp_path / "a_ok.json", [PASSES])
    _write(tmp_path / "b_bad.json", [RAISES])
    _write(tmp_path / "c_bad.json", [RAISES])
    assert cli_main.main(["-d", str(tmp_path)]) == 1  # nosec B101
    assert "error: 2 action(s) or file(s) failed" in capsys.readouterr().err  # nosec B101


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
    assert cli_main.main(["-d", str(tmp_path), "--parallel", "2", "--parallel-mode", "process"]) == 1  # nosec B101


def test_async_failed_files_are_counted_once(tmp_path, monkeypatch, capsys):
    from je_web_runner.utils.async_executor import executor as async_executor

    _write(tmp_path / "a.json", [PASSES])
    _write(tmp_path / "b.json", [PASSES])
    monkeypatch.setattr(async_executor, "run_action_lists", lambda *args, **kwargs: [
        ({"first": "failed", "second": "failed"}, ["first", "second"]),
        ({"third": "passed"}, []),
    ])
    assert cli_main.main(["-d", str(tmp_path), "--parallel-mode", "async"]) == 1  # nosec B101
    assert "error: 1 action(s) or file(s) failed" in capsys.readouterr().err  # nosec B101


def test_thread_failures_are_counted(tmp_path, capsys):
    for index in range(8):
        _write(tmp_path / f"{index}.json", [RAISES, PASSES])
    assert cli_main.main(["-d", str(tmp_path), "--parallel", "4"]) == 1  # nosec B101
    captured = capsys.readouterr()
    assert "error: 8 action(s) or file(s) failed" in captured.err  # nosec B101
    assert captured.out.count("failure-count-test") >= 8  # nosec B101


@pytest.mark.parametrize("flags", [[], ["--ledger"], ["--parallel", "2"]], ids=["sequential", "ledger", "thread"])
def test_unreadable_file_fails_run_and_remaining_files_run(tmp_path, capsys, flags):
    actions = tmp_path / "actions"
    actions.mkdir()
    (actions / "a_bad.json").write_text("{invalid", encoding="utf-8")
    _write(actions / "b_ok.json", [PASSES])
    if flags == ["--ledger"]:
        flags = [*flags, str(tmp_path / "ledger.json")]
    assert cli_main.main(["-d", str(actions), *flags]) == 1  # nosec B101
    captured = capsys.readouterr()
    assert "error: 1 action(s) or file(s) failed" in captured.err  # nosec B101
    assert "failure-count-test" in captured.out  # nosec B101


def test_ledger_detects_failed_actions_without_recording(tmp_path, monkeypatch):
    from je_web_runner.utils.run_ledger.ledger import latest_status
    from je_web_runner.utils.test_record.test_record_class import test_record_instance

    monkeypatch.setattr(test_record_instance, "init_record", False)
    actions = tmp_path / "actions"
    actions.mkdir()
    bad = _write(actions / "bad.json", [RAISES])
    good = _write(actions / "good.json", [PASSES])
    ledger = str(tmp_path / "ledger.json")
    assert cli_main.main(["-d", str(actions), "--ledger", ledger]) == 1  # nosec B101
    assert latest_status(ledger) == {bad: False, good: True}  # nosec B101


def test_dependency_failure_skips_downstream_without_recording(tmp_path, monkeypatch, capsys):
    from je_web_runner.utils.test_record.test_record_class import test_record_instance

    monkeypatch.setattr(test_record_instance, "init_record", False)
    _write(tmp_path / "upstream.json", [RAISES])
    _write(tmp_path / "downstream.json", {
        "meta": {"depends_on": ["upstream"]},
        "webdriver_wrapper": [["print", ["must-not-run-downstream"]]],
    })
    assert cli_main.main(["-d", str(tmp_path)]) == 1  # nosec B101
    assert "must-not-run-downstream" not in capsys.readouterr().out  # nosec B101


def test_async_unreadable_file_does_not_stop_other_files(tmp_path, monkeypatch, capsys):
    from je_web_runner.utils.async_executor import executor as async_executor

    (tmp_path / "a_bad.json").write_text("{invalid", encoding="utf-8")
    _write(tmp_path / "b_good.json", [PASSES])
    def run_loaded(actions, **kwargs):
        assert actions == [[PASSES]]  # nosec B101
        return [({"passed": "async-continued"}, [])]
    monkeypatch.setattr(async_executor, "run_action_lists", run_loaded)
    assert cli_main.main(["-d", str(tmp_path), "--parallel-mode", "async"]) == 1  # nosec B101
    captured = capsys.readouterr()
    assert "async-continued" in captured.out  # nosec B101
    assert "error: 1 action(s) or file(s) failed" in captured.err  # nosec B101
