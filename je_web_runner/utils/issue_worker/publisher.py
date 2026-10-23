"""Host-only, resumable GitHub tree/commit/ref and pull request publication."""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable
from urllib.parse import quote

from je_web_runner.utils.issue_worker.providers import GitHubIssues
from je_web_runner.utils.issue_worker.types import IssueWorkerError
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace, git_run


class GitHubPublisher:
    """Publish only an independently validated tree; credentials never enter the worktree."""

    def __init__(self, provider: GitHubIssues) -> None:
        self.provider = provider
        self.client = provider.client
        self.config = provider.config
        self.prefix = provider.prefix

    def preflight(self) -> None:
        """Verify the trusted GitHub publishing identity."""
        self.provider.authorize()

    def publish(self, workspace: IssueWorkspace, job: dict[str, Any],
                checkpoint: Callable[[str, dict[str, Any]], None]) -> dict[str, Any]:
        """Reconcile before writes, including a PR created before an ambiguous timeout."""
        data = job["data"]
        branch = data.setdefault("branch", "automation/" + job["key"].replace(":", "-") + f"-r{job['run']}")
        checkpoint("publishing", data)
        existing = self._existing(branch, job)
        if existing:
            return existing
        workspace.verify_scope()
        if data.get("validated_tree") != workspace.fingerprint() or not workspace.changes():
            raise IssueWorkerError("publication requires unchanged, independently validated content")
        if not all(data.get("checks", {}).get(name, {}).get("passed") and
                   data["checks"][name].get("tree") == data["validated_tree"] for name in self.config.checks):
            raise IssueWorkerError("required check results do not match the publication tree")
        self.preflight()
        current_base = self.client.request("GET", self.prefix + "/git/ref/heads/" + self.config.base_branch)
        if current_base["object"]["sha"] != workspace.base_sha:
            raise IssueWorkerError("dev advanced since validation; retry against the new baseline")
        self._commit(workspace, job, checkpoint)
        self._reference(job, checkpoint)
        result = self._write(self.prefix + "/pulls", {
            "title": f"Resolve {job['key']}: {job['snapshot']['title']}"[:240],
            "head": branch, "base": self.config.base_branch, "body": self._body(job),
        }, job, checkpoint)
        return {"url": result["html_url"], "number": result["number"], "head": data["remote_commit"]}

    def _existing(self, branch: str, job: dict[str, Any]) -> dict[str, Any] | None:
        owner = self.config.repository.split("/")[0]
        rows = self.client.request("GET", self.prefix + "/pulls", params={
            "head": owner + ":" + branch, "base": self.config.base_branch, "state": "all", "per_page": 100,
        })
        if not rows:
            return None
        marker = self._marker(job)
        for row in rows:
            if marker not in (row.get("body") or "") or row.get("user", {}).get("login", "").casefold() != \
                    self.config.github_bot.casefold():
                raise IssueWorkerError("publication branch already has a PR not owned by this worker run")
            if row["state"] != "open":
                raise IssueWorkerError("this run's PR was closed; automatic reopening is not allowed")
            if row["head"]["sha"] != job["data"].get("remote_commit"):
                raise IssueWorkerError("PR head changed after validation; refusing to adopt unvalidated content")
            return {"url": row["html_url"], "number": row["number"], "head": row["head"]["sha"]}
        return None

    def _commit(self, workspace: IssueWorkspace, job: dict[str, Any],
                checkpoint: Callable[[str, dict[str, Any]], None]) -> None:
        data = job["data"]
        if data.get("remote_commit"):
            return
        base = self.client.request("GET", self.prefix + "/git/commits/" + workspace.base_sha)
        entries = self._entries(workspace)
        tree = self._write(self.prefix + "/git/trees", {
            "base_tree": base["tree"]["sha"], "tree": entries,
        }, job, checkpoint)
        if tree["sha"] != data["validated_tree"]:
            raise IssueWorkerError("remote tree differs from the validated local tree")
        date = datetime.fromtimestamp(job["created"], timezone.utc).isoformat()
        author = {"name": self.config.github_bot, "email": self.config.github_bot + "@users.noreply.github.com",
                  "date": date}
        commit = self._write(self.prefix + "/git/commits", {
            "message": f"Resolve {job['key']}", "tree": tree["sha"], "parents": [workspace.base_sha],
            "author": author, "committer": author,
        }, job, checkpoint)
        # Timestamp/author/message/tree/parent are fixed, so retrying an uncertain commit response is content-addressed.
        data["remote_commit"] = commit["sha"]
        checkpoint("publishing", data)

    def _reference(self, job: dict[str, Any], checkpoint: Callable[[str, dict[str, Any]], None]) -> None:
        data = job["data"]
        reference = self.prefix + "/git/ref/heads/" + quote(data["branch"], safe="/")
        current = self.client.request("GET", reference, missing_ok=True)
        if current:
            sha = current["object"]["sha"]
            if sha != data["remote_commit"]:
                raise IssueWorkerError("publication branch was changed externally; refusing to overwrite it")
            return
        self._write(self.prefix + "/git/refs", {
            "ref": "refs/heads/" + data["branch"], "sha": data["remote_commit"],
        }, job, checkpoint)

    def _write(self, path: str, payload: dict[str, Any], job: dict[str, Any],
               checkpoint: Callable[[str, dict[str, Any]], None]) -> Any:
        checkpoint("publishing", job["data"])
        if time.time() >= job["data"]["deadline"]:
            raise IssueWorkerError("issue deadline expired before publication")
        return self.client.request("POST", path, payload=payload)

    @staticmethod
    def _entries(workspace: IssueWorkspace) -> list[dict[str, Any]]:
        entries = []
        for _added, _deleted, name in workspace.changes():
            indexed = git_run(workspace.root, ["ls-files", "--stage", "--", name]).strip()
            if not indexed:
                entries.append({"path": name, "mode": "100644", "type": "blob", "sha": None})
                continue
            mode = indexed.split()[0]
            content = git_run(workspace.root, ["show", ":" + name])
            entries.append({"path": name, "mode": mode, "type": "blob", "content": content})
        return entries

    @staticmethod
    def _marker(job: dict[str, Any]) -> str:
        return f"<!-- webrunner-issue:{job['key']}:run-{job['run']} -->"

    def _body(self, job: dict[str, Any]) -> str:
        data = job["data"]
        checks = "\n".join(f"- {name}: passed ({item['tree']})" for name, item in data["checks"].items())
        evidence = "\n\n".join(
            f"{name} output:\n```text\n" + str(item.get("output", ""))[-3000:].replace("```", "'''") + "\n```"
            for name, item in data["checks"].items()
        )
        baseline = data.get("baseline", {})
        return (self._marker(job) + f"\nRelated issue: {job['snapshot']['url']}\n\n"
                + data.get("summary", "Validated issue changes") + "\n\nValidation:\n" + checks
                + f"\n\nBaseline check: {'passed' if baseline.get('passed') else 'failed'}."
                + "\n\n" + evidence
                + "\n\nReview required. This worker does not merge the PR or close the issue.")
