"""Unit tests for the polling watch helper (cli.watch_mode)."""
import pytest

from je_web_runner.utils.cli import watch_mode
from je_web_runner.utils.cli.watch_mode import _snapshot, watch_directory


def test_snapshot_only_tracks_json(tmp_path):
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    (tmp_path / "b.json").write_text("{}", encoding="utf-8")
    (tmp_path / "c.txt").write_text("nope", encoding="utf-8")
    snapshot = _snapshot(str(tmp_path))
    assert len(snapshot) == 2  # nosec B101
    assert all(key.endswith(".json") for key in snapshot)  # nosec B101


def test_watch_missing_dir_raises():
    with pytest.raises(FileNotFoundError):
        watch_directory("does-not-exist-dir", lambda: None)


def test_watch_initial_run_only_when_idle(tmp_path):
    calls = []
    runs = watch_directory(
        str(tmp_path), lambda: calls.append(1),
        poll_seconds=0.01, debounce_seconds=0.01, iterations=1,
    )
    # No file changed, so only the baseline run fires.
    assert runs == 1  # nosec B101
    assert len(calls) == 1  # nosec B101


def test_watch_detects_change_and_reruns(tmp_path):
    calls = []

    def runner():
        calls.append(1)
        if len(calls) == 1:  # create a file during the baseline run
            (tmp_path / "new.json").write_text("{}", encoding="utf-8")

    runs = watch_directory(
        str(tmp_path), runner,
        poll_seconds=0.01, debounce_seconds=0.01, iterations=1,
    )
    assert runs == 2  # nosec B101
    assert len(calls) == 2  # nosec B101


def test_watch_stops_on_keyboard_interrupt(tmp_path):
    calls = []

    def runner():
        calls.append(1)
        if len(calls) == 1:
            (tmp_path / "new.json").write_text("{}", encoding="utf-8")
        elif len(calls) == 2:
            raise KeyboardInterrupt

    runs = watch_directory(
        str(tmp_path), runner,
        poll_seconds=0.01, debounce_seconds=0.01, iterations=5,
    )
    # Second invocation raised before its run was counted; loop exits cleanly.
    assert runs == 1  # nosec B101
    assert len(calls) == 2  # nosec B101


def test_watch_defers_while_still_changing(tmp_path, monkeypatch):
    # initial, iter1-current, iter1-settled (differs -> defer), iter2-current
    snapshots = [
        {"a.json": 1.0},
        {"a.json": 2.0},
        {"a.json": 3.0},
        {"a.json": 3.0},
    ]
    monkeypatch.setattr(watch_mode, "_snapshot", lambda directory: snapshots.pop(0))
    calls = []
    runs = watch_directory(
        str(tmp_path), lambda: calls.append(1),
        poll_seconds=0.0, debounce_seconds=0.0, iterations=2,
    )
    # The directory was still changing during debounce, so no re-run fired.
    assert runs == 1  # nosec B101
    assert len(calls) == 1  # nosec B101
