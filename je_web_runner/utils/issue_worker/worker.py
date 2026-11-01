"""Single-host issue lifecycle: intake, claim, isolated coding, checks and reviewed delivery."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

from je_web_runner.utils.agent.runner import Redactor, browser_privacy
from je_web_runner.utils.issue_worker.inbox import IssueInbox
from je_web_runner.utils.issue_worker.doctor import IssueDoctor
from je_web_runner.utils.issue_worker.metrics import IssueMetrics
from je_web_runner.utils.issue_worker.processor import CodeProcessor
from je_web_runner.utils.issue_worker.publisher import GitHubPublisher
from je_web_runner.utils.issue_worker.runtime import WorkerRuntime, operational_log
from je_web_runner.utils.issue_worker.triage import MANUAL_LABELS
from je_web_runner.utils.issue_worker.reviews import ReviewInbox, owned_pr
from je_web_runner.utils.issue_worker.types import (
    FINAL, EnvironmentUnavailable, IssueSnapshot, IssueWorkerConfig, IssueWorkerError, ProviderError,
)
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class IssueCancelled(IssueWorkerError):
    """Human requirements, eligibility or ownership changed during an automated run."""


class IssueWorker:
    """A trusted host coordinator; model actions never receive publishing credentials."""

    def __init__(self, config: IssueWorkerConfig, providers: dict[str, Any] | None = None,
                 processor: Any = None, publisher: Any = None, workspace_factory: Callable | None = None) -> None:
        self.config = config
        self.inbox = IssueInbox(config, providers)
        self.store = self.inbox.store
        self.runtime = WorkerRuntime(self.store)
        self.processor = processor
        self.publisher = publisher or GitHubPublisher(self.inbox.providers["github"])
        self.workspace_factory = workspace_factory or IssueWorkspace.prepare
        self._watch_stop: threading.Event | None = None
        self.redactor = Redactor()
        self.redactor.secrets.update(os.environ[name] for name in (config.github_token_env, config.jira_token_env)
                                     if os.environ.get(name))

    def close(self) -> None:
        """Close local model and platform clients."""
        if self.processor is not None:
            self.processor.close()
        self.inbox.close()

    def status(self, key: str | None = None) -> list[dict[str, Any]]:
        """Return sanitized durable reports."""
        return self.redactor.clean(self.store.status(key))

    def metrics(self, since_hours: float | None = None, issue: str | None = None) -> dict[str, Any]:
        """Return local delivery history/queue aggregates without platform requests."""
        return self.redactor.clean(IssueMetrics(self.store).summary(since_hours, issue))

    def retry(self, key: str) -> None:
        """Explicitly requeue a stopped issue after the ready label is restored."""
        self.inbox.retry(key)

    def retry_review(self, key: str) -> None:
        """Explicitly re-enable same-PR feedback after a stopped revision; never adopt an external head."""
        if not self.config.review_enabled:
            raise IssueWorkerError("enable review_enabled in host config before retrying review")
        with self.store.lease():
            jobs = self.store.status(key)
            if not jobs or jobs[0]["status"] not in FINAL or not jobs[0]["data"].get("pr"):
                raise IssueWorkerError("review retry requires a terminal job with its saved PR")
            job = jobs[0]
            if job["data"].get("report_pending"):
                raise IssueWorkerError("deliver the pending progress report before retrying review")
            if job["data"].get("review_rounds", 0) >= self.config.max_review_rounds:
                raise IssueWorkerError("review round limit reached; increase the host limit explicitly first")
            provider, snapshot = self.inbox._fetch(key)
            if snapshot.closed or snapshot.assignee != provider.bot or "automation-review" not in snapshot.labels:
                raise IssueWorkerError("review retry requires an open, bot-owned issue with automation-review")
            if MANUAL_LABELS & {label.casefold() for label in snapshot.labels}:
                raise IssueWorkerError("remove manual hold labels before retrying review")
            pr = owned_pr(self.inbox.providers["github"], job)
            if pr["state"] != "open" or pr["head"]["sha"] != job["data"]["pr"]["head"]:
                raise IssueWorkerError("review retry cannot reopen a PR or adopt an external head")
            self.store.resume_review(job, snapshot)

    def health(self) -> dict[str, Any]:
        """Inspect local daemon health without contacting platforms or model services."""
        return self.redactor.clean(self.runtime.health())

    def request_stop(self) -> bool:
        """Drain the active watch instance, completing its current issue before stopping."""
        return self.runtime.request_stop()

    def run_once(self, dry_run: bool = False, discover: bool = True) -> dict[str, Any]:
        """Discover and process at most one job; dry-run does not claim or publish anything."""
        if dry_run:
            return {"preview": self.inbox.discover(dry_run=True)}
        with self.store.lease(), browser_privacy():
            self.runtime.assert_allowed()
            if self._draining():
                return {"status": "idle"}
            job = self._next_job(discover)
            if job is None:
                return {"status": "idle"}
            if not self._begin_job(job["key"]):
                return {"status": "idle"}
            if job["status"] in FINAL:
                self._report(job)
            else:
                self._process_job(job)
            return self.status(job["key"])[0]

    def _next_job(self, discover: bool = True) -> dict[str, Any] | None:
        job = self.store.next_job()
        if discover and (job is None or job["status"] == "queued"):
            self.inbox.discover()
            job = self.store.next_job()
        if self.config.review_enabled and (job is None or job["status"] == "queued"):
            return ReviewInbox(self.inbox.providers["github"], self.redactor).poll(self.store) or job
        return job

    def watch(self, stop: threading.Event | None = None) -> None:
        """Run one fenced local daemon; dependency outages pause intake rather than fail jobs."""
        stopped = stop or threading.Event()
        with self.runtime.own(), operational_log(self.store) as logger:
            self._watch_stop = stopped
            try:
                logger.info("watch started")
                while not self._stopping(stopped):
                    self._watch_poll(logger, stopped)
                    self._wait_poll(stopped)
                logger.info("watch drained")
            finally:
                self._watch_stop = None

    def _draining(self) -> bool:
        return bool(self.runtime.token and (self.runtime.stopping() or
                    (self._watch_stop is not None and self._watch_stop.is_set())))

    def _begin_job(self, key: str) -> bool:
        if self._draining():
            return False
        return not self.runtime.token or self.runtime.begin_job(key)

    def _stopping(self, stop: threading.Event) -> bool:
        return stop.is_set() or self.runtime.stopping()

    def _wait_poll(self, stop: threading.Event) -> None:
        deadline = time.monotonic() + self.config.poll_seconds
        while not self._stopping(stop) and time.monotonic() < deadline:
            stop.wait(min(0.25, max(0, deadline - time.monotonic())))

    def _watch_poll(self, logger: Any, stop: threading.Event) -> None:
        self.runtime.update("checking")
        readiness = IssueDoctor(self.config).check()
        if not readiness["ready"]:
            codes = ",".join(item["code"] for item in readiness["checks"] if item["status"] == "failed")
            self.runtime.update("waiting_dependencies", error=codes)
            logger.warning("intake paused: %s", codes)
            return
        if self._stopping(stop):
            return
        try:
            result = self.run_once()
            error = result.get("data", {}).get("platform_error") or result.get("data", {}).get("environment_error")
            self.runtime.update("waiting" if not error else "deferred", error=error, polled=True)
            logger.info("poll completed: %s", result.get("status", "unknown"))
        except ProviderError as error:
            self.runtime.update("platform_error", error=self.redactor.clean(str(error)))
            logger.warning("platform polling deferred")
            if error.permanent:
                raise

    def _process_job(self, job: dict[str, Any]) -> None:
        provider = self.inbox.providers[job["snapshot"]["source"]]
        try:
            self._execute(job, provider)
        except IssueCancelled as error:
            self._finish(job, "cancelled", str(error))
        except ProviderError as error:
            self._defer(job, error)
            if error.permanent:
                raise
        except EnvironmentUnavailable:
            job["data"]["environment_error"] = "local model or container dependency is unavailable"
            self._save(job, job["status"], time.time() + self.config.poll_seconds)
        except Exception as error:
            message = self.redactor.clean(f"{type(error).__name__}: {error}")
            web_runner_logger.warning("issue processing stopped: %s", message)
            code = "time_budget" if job["data"].get("reason_code") == "time_budget" else "execution_error"
            self._finish(job, "failed", message, code=code)

    def _execute(self, job: dict[str, Any], provider: Any) -> None:
        snapshot = IssueSnapshot(**job["snapshot"])
        data = job["data"]
        self._guard(job, provider, resume=job["status"] != "queued" or job["run"] > 1)
        self.publisher.preflight()
        coding_needed = job["status"] != "publishing" and data.get("phase") != "ready"
        if coding_needed:
            if self.processor is None:
                self.processor = CodeProcessor(self.config)
            self.processor.preflight()
            self.processor.recover()
            data.pop("environment_error", None)
            data.setdefault("started_at", time.time())
            data.setdefault("deadline", time.time() + self.config.timeout)
            self._save(job, "claimed")
            data["claim_started"] = True
            self._save(job, "claimed")
            if not data.get("review"):
                provider.claim(snapshot)
            self._guard(job, provider, resume=True)
            provider.report(snapshot, "analyzing", "Claimed; preparing isolated implementation and validation.")
        workspace = self.workspace_factory(self.config, job)
        data["base_sha"] = workspace.base_sha
        self._save(job, job["status"])

        def checkpoint(status: str, progress: dict[str, Any]) -> None:
            self.store.assert_lease()
            self._guard(job, provider, resume=True)
            job["data"] = progress
            self._save(job, status)
            if data.get("reported_stage") != status:
                provider.report(snapshot, status, f"{status}: isolated implementation and checks are in progress.")
                data["reported_stage"] = status
                self._save(job, status)

        if coding_needed:
            outcome = self.processor.process(job, workspace, checkpoint, self.redactor)
            if outcome != "ready":
                self._finish(job, outcome, data.get("reason", "implementation did not pass validation"))
                return
        self._guard(job, provider, resume=True)
        self._save(job, "publishing")
        deliver = self.publisher.revise if data.get("review") else self.publisher.publish
        data["pr"] = deliver(workspace, job, checkpoint)
        if data.get("review"):
            self.store.finish_review(job)
        data.pop("platform_error", None)
        self._finish(job, "awaiting_review", "Validated changes are ready for human review.")

    def _guard(self, job: dict[str, Any], provider: Any, resume: bool) -> None:
        self.runtime.assert_allowed()
        self.store.assert_lease()
        current = provider.fetch(job["snapshot"]["external_id"])
        expected = IssueSnapshot(**job["snapshot"])
        eligible = current.eligible(provider.bot, resume=resume)
        if job["data"].get("review"):
            pr = owned_pr(self.inbox.providers["github"], job)
            allowed_heads = {job["data"]["review"]["parent"], job["data"].get("remote_commit")}
            if pr["state"] != "open" or pr["head"]["sha"] not in allowed_heads:
                raise IssueCancelled("PR was closed or changed during automated revision")
            eligible = not current.closed and current.assignee == provider.bot and bool(
                {"automation-review", "automation-running"} & set(current.labels))
        if not eligible or current.revision != expected.revision:
            raise IssueCancelled("issue requirements, ready label, open state or ownership changed")
        if MANUAL_LABELS & {label.casefold() for label in current.labels}:
            raise IssueCancelled("issue was explicitly placed on manual hold")

    def _save(self, job: dict[str, Any], status: str, next_attempt: float = 0) -> None:
        self.runtime.assert_allowed()
        self.store.assert_lease()
        job["status"] = status
        self.store.save(job["key"], status, self.redactor.clean(job["data"]), next_attempt)
        if self.runtime.token:
            error = job["data"].get("environment_error") or job["data"].get("platform_error")
            self.runtime.update(status, job["key"], error)

    def _finish(self, job: dict[str, Any], status: str, reason: str, code: str = "") -> None:
        if status not in FINAL:
            raise IssueWorkerError("processor returned an invalid terminal outcome")
        job["data"]["reason"] = self.redactor.clean(reason)
        known = {"awaiting_review": "delivered", "cancelled": "cancelled", "needs_info": "requirements_clarification"}
        job["data"]["reason_code"] = known.get(status) or code or job["data"].get("reason_code", status)
        job["data"].setdefault("finished_at", time.time())
        job["data"]["report_pending"] = bool(job["data"].get("claim_started"))
        self._save(job, status)
        self._record_outcome(job)
        self._write_artifact(job)
        if job["data"]["report_pending"]:
            self._report(job)

    def _report(self, job: dict[str, Any]) -> None:
        if not job["data"].get("report_pending"):
            return
        self._record_outcome(job)
        provider = self.inbox.providers[job["snapshot"]["source"]]
        message = job["status"] + ": " + job["data"].get("reason", "")
        if job["data"].get("pr"):
            message += "\nPR: " + job["data"]["pr"]["url"]
        try:
            self.runtime.assert_allowed()
            self.store.assert_lease()
            provider.report(IssueSnapshot(**job["snapshot"]), job["status"], self.redactor.clean(message))
            job["data"]["report_pending"] = False
            job["data"].pop("platform_error", None)
            self._save(job, job["status"])
            self._write_artifact(job)
        except ProviderError as error:
            self._defer(job, error)
            if error.permanent:
                raise

    def _defer(self, job: dict[str, Any], error: ProviderError) -> None:
        job["data"]["platform_error"] = str(error)
        self._save(job, job["status"], time.time() + max(60, error.retry_after))

    def _record_outcome(self, job: dict[str, Any]) -> None:
        try:
            self.store.record_outcome(job)
        except sqlite3.Error as error:
            web_runner_logger.warning("issue metrics unavailable: %s", type(error).__name__)

    def _write_artifact(self, job: dict[str, Any]) -> None:
        try:
            root = Path(self.config.state_dir) / "reports"
            root.mkdir(parents=True, exist_ok=True)
            path = root / (job["key"].replace(":", "-") + f"-r{job['run']}.json")
            path.write_text(json.dumps(self.redactor.clean(job), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as error:
            web_runner_logger.warning("issue artifact unavailable: %s", type(error).__name__)
