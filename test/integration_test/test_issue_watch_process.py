"""Real child-process termination/restart and local CLI drain with short fixture lease timings."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from je_web_runner.utils.issue_worker.runtime import WorkerRuntime
from je_web_runner.utils.issue_worker.store import IssueStore

CHILD = '''
import sys
from unittest.mock import patch
import je_web_runner.utils.issue_worker.runtime as runtime
from je_web_runner.utils.issue_worker import IssueWorker, IssueWorkerConfig
runtime.HEARTBEAT_SECONDS = 0.03
runtime.STALE_SECONDS = 0.5
worker = IssueWorker(IssueWorkerConfig(sys.argv[1], "fixture", "worker-bot", poll_seconds=0.05))
worker.run_once = lambda: {"status": "idle"}
try:
    with patch("je_web_runner.utils.issue_worker.worker.IssueDoctor") as doctor:
        doctor.return_value.check.return_value = {"ready": True}
        worker.watch()
finally:
    worker.close()
'''


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        threading.Event().wait(0.03)
    return False


def test_watch_process_crash_restart_and_cli_stop(tmp_path, monkeypatch):
    monkeypatch.setattr("je_web_runner.utils.issue_worker.runtime.STALE_SECONDS", 0.5)
    state = tmp_path / "state"
    runtime = WorkerRuntime(IssueStore(state))
    environment = dict(os.environ, WEBRUNNER_LOG_PATH=os.devnull)
    processes = []

    def launch():
        process = subprocess.Popen([sys.executable, "-c", CHILD, str(state)], env=environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(process)
        return process

    try:
        first = launch()
        assert wait_for(lambda: runtime.health()["status"] == "healthy")
        first_instance = runtime.health()["instance"]
        duplicate = launch()
        assert duplicate.wait(timeout=15) != 0
        first.kill()
        first.wait(timeout=5)
        assert wait_for(lambda: runtime.health()["status"] == "stale")
        successor = launch()
        assert wait_for(lambda: runtime.health().get("instance") != first_instance and
                        runtime.health()["status"] == "healthy")
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"state_dir": str(state), "model": "fixture", "github_bot": "worker-bot"}),
                          encoding="utf-8")
        stopped = subprocess.run([sys.executable, "-m", "je_web_runner.issue_worker", "stop", "--config", str(config)],
                                 capture_output=True, env=environment, timeout=15, check=False)
        assert stopped.returncode == 0 and json.loads(stopped.stdout)["stop_requested"] is True
        assert successor.wait(timeout=15) == 0
        assert runtime.health()["status"] == "stopped"
        assert runtime.request_stop() is False
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
    assert (Path(state) / "logs/worker.log").exists()
