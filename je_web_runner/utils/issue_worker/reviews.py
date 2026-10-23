"""Trusted GitHub feedback intake and durable, bounded revisions of an existing PR."""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Iterable
from urllib.parse import quote

from je_web_runner.utils.agent.runner import Redactor
from je_web_runner.utils.issue_worker.providers import GitHubIssues
from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.types import IssueWorkerError, ProviderError

_FAILURES = {"failure", "timed_out", "action_required", "startup_failure"}


def owned_pr(provider: GitHubIssues, job: dict[str, Any]) -> dict[str, Any]:
    """Require the exact bot-owned PR, run marker, repository, branch and review target."""
    number = job["data"]["pr"]["number"]
    if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
        raise IssueWorkerError("invalid saved PR number")
    row = provider.client.request("GET", provider.prefix + f"/pulls/{number}")
    if not isinstance(row, dict):
        raise IssueWorkerError("invalid GitHub PR response")
    head, base = row.get("head") or {}, row.get("base") or {}
    expected = provider.config.repository.casefold()
    marker = f"<!-- webrunner-issue:{job['key']}:run-{job['run']} -->"
    checks = (
        row.get("user", {}).get("login", "").casefold() == provider.bot.casefold(),
        marker in (row.get("body") or ""),
        head.get("ref") == job["data"]["branch"],
        (head.get("repo") or {}).get("full_name", "").casefold() == expected,
        base.get("ref") == provider.config.base_branch,
        (base.get("repo") or {}).get("full_name", "").casefold() == expected,
        row.get("state") in {"open", "closed"},
    )
    if not all(checks):
        raise IssueWorkerError("PR ownership, branch or repository changed")
    return row


class ReviewInbox:
    """Read feedback as untrusted requirements, never as host commands or check argv."""

    def __init__(self, provider: GitHubIssues, redactor: Redactor) -> None:
        self.provider = provider
        self.config = provider.config
        self.redactor = redactor

    def poll(self, store: IssueStore) -> dict[str, Any] | None:
        """Inspect at most one due PR, returning a checkpointed revision when feedback is new."""
        candidates = [job for job in store.status() if self._due(job)]
        if not candidates:
            return None
        job = min(candidates, key=lambda item: item["data"].get("review_polled", 0))
        data = job["data"]
        data["review_polled"] = time.time()
        try:
            return self._poll_job(store, job)
        except ProviderError:
            raise
        except IssueWorkerError as error:
            data["review_blocked"] = self.redactor.clean(str(error))
            return None
        finally:
            if job["status"] == "awaiting_review":
                store.assert_lease()
                store.save(job["key"], job["status"], self.redactor.clean(data))

    def _due(self, job: dict[str, Any]) -> bool:
        data = job["data"]
        return bool(job["status"] == "awaiting_review" and data.get("pr") and
                    not data.get("report_pending") and not data.get("review_closed") and
                    not data.get("review_blocked") and
                    data.get("review_polled", 0) + self.config.review_poll_seconds <= time.time())

    def _poll_job(self, store: IssueStore, job: dict[str, Any]) -> dict[str, Any] | None:
        data = job["data"]
        if not data["pr"].get("head"):
            raise IssueWorkerError("saved PR head is missing; manual reconciliation is required")
        pr = owned_pr(self.provider, job)
        if pr["state"] != "open":
            data["review_closed"] = "merged" if pr.get("merged") else "closed"
            return None
        if pr["head"]["sha"] != data["pr"]["head"]:
            raise IssueWorkerError("PR head changed outside this worker")
        events = self._events(pr, store.review_seen(job["key"], job["run"]))
        if not events:
            return None
        round_number = data.get("review_rounds", 0) + 1
        if round_number > self.config.max_review_rounds:
            raise IssueWorkerError("review round limit reached; human intervention is required")
        original = data.get("original_base_sha", data["base_sha"])
        current = self.provider.client.request("GET", self.provider.prefix + "/git/ref/heads/" +
                                               self.config.base_branch)
        if current["object"]["sha"] != original:
            raise IssueWorkerError("dev advanced; rebase and validate manually before further automation")
        self._start(store, job, events, original, round_number)
        return job

    def _start(self, store: IssueStore, job: dict[str, Any], events: list[dict[str, Any]],
               original: str, round_number: int) -> None:
        data = job["data"]
        # Preserve delivery identity and immutable source requirements; reset only per-revision coding state.
        retained = {name: data[name] for name in ("pr", "branch", "claim_started", "review_polled") if name in data}
        retained.update({"original_base_sha": original, "review_rounds": round_number,
                         "base_sha": data["pr"]["head"],
                         "review": {"parent": data["pr"]["head"], "round": round_number,
                                    "started": time.time(), "feedback": events}})
        data.clear()
        data.update(self.redactor.clean(retained))
        store.start_review(job, events)

    def _events(self, pr: dict[str, Any], seen: set[str]) -> list[dict[str, Any]]:
        prefix = self.provider.prefix
        number, head = pr["number"], pr["head"]["sha"]
        permissions: dict[str, bool] = {}
        reviews = list(self._rows(prefix + f"/pulls/{number}/reviews"))
        latest = {(row.get("user") or {}).get("login"): row for row in reviews}
        actionable = {row["id"] for row in latest.values()
                      if row.get("state") in {"CHANGES_REQUESTED", "COMMENTED"}}
        rows = [("review", row) for row in reviews if row.get("id") in actionable]
        rows += [("inline", row) for row in self._rows(prefix + f"/pulls/{number}/comments")
                 if row.get("pull_request_review_id") in actionable]
        rows += [("comment", row) for row in self._rows(prefix + f"/issues/{number}/comments")
                 if re.match(r"^/webrunner fix(?:\s|$)", (row.get("body") or "").lstrip())]
        events = []
        for kind, row in rows:
            if kind != "comment" and row.get("commit_id") != head:
                continue
            if not isinstance(row.get("body"), str) or not row["body"] or \
                    not self._trusted(row.get("user") or {}, permissions):
                continue
            body = row["body"]
            if kind == "comment":
                body = body.lstrip()[len("/webrunner fix"):].strip()
            body = f"{row.get('path', '')}:{row.get('line', '')}\n" + body
            events.append(self._event(kind, row, head, body))
        events.extend(self._checks(head))
        unique = {event["key"]: event for event in events if event["key"] not in seen}
        result = list(unique.values())
        if len(result) > 50 or sum(len(event["body"]) for event in result) > 20000:
            raise IssueWorkerError("review batch exceeds its limit; summarize feedback before retrying review")
        return result

    def _trusted(self, user: dict[str, Any], cache: dict[str, bool]) -> bool:
        login = user.get("login", "")
        if not login or user.get("type") != "User" or login.casefold() == self.provider.bot.casefold():
            return False
        if login not in cache:
            result = self.provider.client.request("GET", self.provider.prefix + "/collaborators/" +
                                                  quote(login, safe="") + "/permission")
            cache[login] = result.get("permission") in {"admin", "maintain", "write"}
        return cache[login]

    def _checks(self, head: str) -> list[dict[str, Any]]:
        prefix = self.provider.prefix + "/commits/" + quote(head, safe="")
        events = []
        for row in self._rows(prefix + "/check-runs", "check_runs", {"filter": "latest"}):
            if row.get("head_sha") == head and row.get("status") == "completed" and \
                    row.get("conclusion") in _FAILURES:
                output = row.get("output") or {}
                body = str(row.get("name", "")) + "\n" + str(output.get("summary") or "")
                events.append(self._event("check", row, head, body))
        latest: dict[str, dict[str, Any]] = {}
        for row in self._rows(prefix + "/statuses"):
            latest.setdefault(row.get("context", ""), row)
        for row in latest.values():
            if row.get("state") in {"failure", "error"}:
                events.append(self._event("status", row, head,
                                          str(row.get("context", "")) + "\n" + str(row.get("description") or "")))
        return events

    def _event(self, kind: str, row: dict[str, Any], head: str, body: str) -> dict[str, Any]:
        cleaned = self.redactor.clean(body)
        if len(cleaned) > 4000:
            raise IssueWorkerError("single review feedback exceeds 4000 characters; summarize before retrying review")
        payload = [kind, str(row["id"]), "" if kind == "comment" else head, cleaned]
        digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
        return {"key": digest, "kind": kind, "head": head, "body": cleaned}

    def _rows(self, path: str, field: str = "", params: dict[str, Any] | None = None
              ) -> Iterable[dict[str, Any]]:
        seen = set()
        for page in range(1, 26):
            response = self.provider.client.request("GET", path, params={**(params or {}), "per_page": 100,
                                                                         "page": page})
            rows = response.get(field) if field and isinstance(response, dict) else response
            if not isinstance(rows, list) or not all(isinstance(row, dict) and "id" in row for row in rows):
                raise IssueWorkerError("invalid GitHub feedback page")
            signature = tuple(str(row.get("id")) for row in rows)
            if rows and signature in seen:
                raise IssueWorkerError("GitHub repeated a feedback page")
            seen.add(signature)
            yield from rows
            if len(rows) < 100:
                return
        raise IssueWorkerError("GitHub feedback pagination exceeded its bounded limit")
