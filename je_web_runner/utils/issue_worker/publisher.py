"""Host-only, resumable GitHub tree/commit/ref and pull request publication."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from typing import Any, Callable
from urllib.parse import quote

from je_web_runner.utils.issue_worker.providers import GitHubIssues
from je_web_runner.utils.issue_worker.reviews import owned_pr
from je_web_runner.utils.issue_worker.requirements import (
    RequirementPlan, criterion_evidence, requirement_revision,
)
from je_web_runner.utils.issue_worker.types import IssueWorkerError, ProviderError
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
        self._validate_workspace(workspace, job)
        existing = self._existing(branch, job)
        if existing:
            return existing
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

    def revise(self, workspace: IssueWorkspace, job: dict[str, Any],
               checkpoint: Callable[[str, dict[str, Any]], None]) -> dict[str, Any]:
        """Fast-forward the same owned PR, reconciling ambiguous ref/comment writes before retry."""
        data = job["data"]
        checkpoint("publishing", data)
        row = owned_pr(self.provider, job)
        parent = data["review"]["parent"]
        if row["state"] != "open" or row["head"]["sha"] not in {parent, data.get("remote_commit")}:
            raise IssueWorkerError("PR was closed or changed outside this revision")
        if workspace.base_sha != parent:
            raise IssueWorkerError("revision workspace does not match its saved PR parent")
        self._validate_workspace(workspace, job)
        self.preflight()
        base = self.client.request("GET", self.prefix + "/git/ref/heads/" + self.config.base_branch)
        if base["object"]["sha"] != data["original_base_sha"]:
            raise IssueWorkerError("dev advanced during review validation")
        self._commit(workspace, job, checkpoint)
        self._advance(job, checkpoint)
        row = owned_pr(self.provider, job)
        if row["state"] != "open":
            raise IssueWorkerError("PR closed during revision delivery")
        if row["head"]["sha"] != data["remote_commit"]:
            raise ProviderError("PR head update is not visible yet", retry_after=15)
        self._revision_comment(job, checkpoint)
        return {"url": row["html_url"], "number": row["number"], "head": data["remote_commit"]}

    def _validate_workspace(self, workspace: IssueWorkspace, job: dict[str, Any]) -> None:
        data = job["data"]
        workspace.verify_scope()
        if data.get("validated_tree") != workspace.fingerprint() or not workspace.changes():
            raise IssueWorkerError("publication requires unchanged, independently validated content")
        if not all(data.get("checks", {}).get(name, {}).get("passed") and
                   data["checks"][name].get("tree") == data["validated_tree"] for name in self.config.checks):
            raise IssueWorkerError("required check results do not match the publication tree")
        self._validate_acceptance(job)

    def _validate_acceptance(self, job: dict[str, Any]) -> None:
        data = job["data"]
        tree = data["validated_tree"]
        if self.config.requirements_enabled:
            analysis = data.get("analysis", {})
            RequirementPlan.parse({key: analysis.get(key) for key in
                                   ("summary", "kind", "criteria", "questions")}, self.config)
            expected = requirement_revision(job["snapshot"], data.get("review", {}).get("feedback", []))
            if not analysis.get("criteria") or analysis.get("questions") or analysis.get("revision") != expected:
                raise IssueWorkerError("publication requires a complete acceptance plan and matching evidence")
            evidence = {"tree": tree, "criteria": criterion_evidence(analysis, data, tree)}
            if data.get("acceptance") != evidence or any(row["status"] == "failed" for row in evidence["criteria"]):
                raise IssueWorkerError("acceptance evidence does not match the validated tree")
        if not self.config.browser_scenarios:
            return
        from je_web_runner.utils.issue_worker.browser_acceptance import BrowserAcceptance
        validator = BrowserAcceptance(self.config)
        for name in self.config.browser_scenarios:
            result = data.get("browser_checks", {}).get(name, {})
            if not result.get("passed") or result.get("tree") != tree or \
                    result.get("signature") != validator.signature(name):
                raise IssueWorkerError("publication requires every current host browser scenario to pass")
            evidence = result.get("evidence", {})
            if evidence.get("status") != "success" or evidence.get("conditions_verified") != \
                    len(self.config.browser_scenarios[name]["task"]["success"]):
                raise IssueWorkerError("browser evidence does not prove the configured condition count")

    def _advance(self, job: dict[str, Any], checkpoint: Callable[[str, dict[str, Any]], None]) -> None:
        data = job["data"]
        path = self.prefix + "/git/ref/heads/" + quote(data["branch"], safe="/")
        current = self.client.request("GET", path)
        head = current["object"]["sha"]
        if head == data["remote_commit"]:
            return
        if head != data["review"]["parent"]:
            raise IssueWorkerError("revision branch changed externally")
        path = self.prefix + "/git/refs/heads/" + quote(data["branch"], safe="/")
        self._mutation("PATCH", path, {"sha": data["remote_commit"], "force": False}, job, checkpoint)

    def _revision_comment(self, job: dict[str, Any], checkpoint: Callable[[str, dict[str, Any]], None]) -> None:
        data = job["data"]
        path = self.prefix + f"/issues/{data['pr']['number']}/comments"
        marker = f"<!-- webrunner-revision:{job['key']}:r{job['run']}:{data['review']['round']} -->"
        rows = self.provider._pages(path)
        if any((row.get("body") or "").startswith(marker + "\n") and
               row.get("user", {}).get("login", "").casefold() == self.config.github_bot.casefold() for row in rows):
            return
        payload = {"body": marker + "\n" + self._body(job)}
        self._write(path, payload, job, checkpoint)

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
        created = data.get("review", {}).get("started", job["created"])
        date = datetime.fromtimestamp(created, timezone.utc).isoformat()
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
        return self._mutation("POST", path, payload, job, checkpoint)

    def _mutation(self, method: str, path: str, payload: dict[str, Any], job: dict[str, Any],
                  checkpoint: Callable[[str, dict[str, Any]], None]) -> Any:
        checkpoint("publishing", job["data"])
        if time.time() >= job["data"]["deadline"]:
            raise IssueWorkerError("issue deadline expired before publication")
        return self.client.request(method, path, payload=payload)

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
                + "\n\n" + self._acceptance_body(data)
                + "\n\nReview required. This worker does not merge the PR or close the issue.")

    @staticmethod
    def _acceptance_body(data: dict[str, Any]) -> str:
        if not data.get("acceptance") and not data.get("browser_checks"):
            return ""
        payload = {"acceptance": data.get("acceptance"),
                   "browser_checks": {name: {field: result.get(field) for field in
                                             ("passed", "tree", "signature", "evidence")}
                                      for name, result in data.get("browser_checks", {}).items()}}
        return "Acceptance evidence (business review remains required):\n```json\n" + \
            json.dumps(payload, ensure_ascii=False, indent=2).replace("```", "'''") + "\n```"
