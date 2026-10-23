"""Run, watch, inspect or explicitly retry local issue jobs."""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from typing import Sequence

from je_web_runner.utils.issue_worker import IssueWorkerConfig
from je_web_runner.utils.issue_worker.doctor import IssueDoctor
from je_web_runner.utils.issue_worker.runtime import WorkerRuntime
from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.worker import IssueWorker


def main(argv: Sequence[str] | None = None) -> int:
    """Keep this CLI independent of the legacy browser execution flags."""
    parser = argparse.ArgumentParser(prog="python -m je_web_runner.issue_worker")
    parser.add_argument("command", choices=("run", "watch", "status", "retry", "doctor", "health", "stop"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--issue", help="github:123 or jira:PROJECT-123")
    parser.add_argument("--dry-run", action="store_true", help="read eligible issues; no claims, changes or PRs")
    parser.add_argument("--platform", action="store_true", help="doctor: also read configured platforms")
    parser.add_argument("--json", action="store_true", help="doctor/health: machine-readable output")
    args = parser.parse_args(argv)
    if args.command == "retry" and not args.issue:
        parser.error("retry requires --issue")
    if args.dry_run and args.command != "run":
        parser.error("--dry-run is only supported with run")
    if args.platform and args.command != "doctor":
        parser.error("--platform is only supported with doctor")
    if args.json and args.command not in {"doctor", "health"}:
        parser.error("--json is only supported with doctor or health")
    config = IssueWorkerConfig.load(args.config)
    if args.command == "doctor":
        result = IssueDoctor(config).check(include_platform=args.platform)
        _diagnostics(result, args.json)
        return 0 if result["ready"] else 1
    if args.command in {"health", "stop"}:
        return _control(WorkerRuntime(IssueStore(config.state_dir)), args)
    worker = IssueWorker(config)
    try:
        return _dispatch(worker, args)
    finally:
        worker.close()


def _dispatch(worker: IssueWorker, args: argparse.Namespace) -> int:
    if args.command == "watch":
        _watch(worker)
        return 0
    if args.command == "status":
        print(json.dumps(worker.status(args.issue), ensure_ascii=False))
        return 0
    if args.command == "retry":
        worker.retry(args.issue)
        print(json.dumps({"queued": args.issue}))
        return 0
    result = worker.run_once(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False))
    failed = result.get("status") in {"failed", "needs_info", "cancelled"}
    data = result.get("data", {})
    deferred = bool(data.get("report_pending") or data.get("platform_error") or data.get("environment_error"))
    return 1 if failed or deferred else 0


def _diagnostics(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
        return
    for item in result["checks"]:
        print(f"{item['status']}: {item['name']} ({item['code']}) {item['hint']}")


def _control(runtime: WorkerRuntime, args: argparse.Namespace) -> int:
    if args.command == "stop":
        print(json.dumps({"stop_requested": runtime.request_stop()}))
        return 0
    health = runtime.health()
    print(json.dumps(health, ensure_ascii=False) if args.json else
          f"{health['status']}: phase={health.get('phase', 'stopped')} "
          f"issue={health.get('current_issue') or '-'} error={health.get('error') or '-'}")
    return {"healthy": 0, "degraded": 1}.get(health["status"], 2)


def _watch(worker: IssueWorker) -> None:
    stop = threading.Event()

    def interrupt(_signum: int, _frame: object) -> None:
        if stop.is_set():
            raise KeyboardInterrupt
        stop.set()

    previous = signal.signal(signal.SIGINT, interrupt)
    try:
        worker.watch(stop)
    finally:
        signal.signal(signal.SIGINT, previous)


def run() -> int:
    """Report sanitized failures without dumping credentials, config contents or stack traces."""
    try:
        return main()
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        # Provider/worker exceptions deliberately omit HTTP response bodies and auth values.
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run())
