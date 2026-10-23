"""Run, watch, inspect or explicitly retry local issue jobs."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from je_web_runner.utils.issue_worker import IssueWorkerConfig
from je_web_runner.utils.issue_worker.worker import IssueWorker


def main(argv: Sequence[str] | None = None) -> int:
    """Keep this CLI independent of the legacy browser execution flags."""
    parser = argparse.ArgumentParser(prog="python -m je_web_runner.issue_worker")
    parser.add_argument("command", choices=("run", "watch", "status", "retry"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--issue", help="github:123 or jira:PROJECT-123")
    parser.add_argument("--dry-run", action="store_true", help="read eligible issues; no claims, changes or PRs")
    args = parser.parse_args(argv)
    if args.command == "retry" and not args.issue:
        parser.error("retry requires --issue")
    if args.dry_run and args.command != "run":
        parser.error("--dry-run is only supported with run")
    worker = IssueWorker(IssueWorkerConfig.load(args.config))
    try:
        return _dispatch(worker, args)
    finally:
        worker.close()


def _dispatch(worker: IssueWorker, args: argparse.Namespace) -> int:
    if args.command == "watch":
        worker.watch()
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
    deferred = bool(result.get("data", {}).get("report_pending") or result.get("data", {}).get("platform_error"))
    return 1 if failed or deferred else 0


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
