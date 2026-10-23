"""Issue discovery and explicit queue control, without starting a coding process."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.issue_worker.providers import GitHubIssues, JiraIssues
from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.types import IssueSnapshot, IssueWorkerConfig, IssueWorkerError


class IssueInbox:
    """One configured repository and optional Jira project allowlist."""

    def __init__(self, config: IssueWorkerConfig, providers: dict[str, Any] | None = None,
                 store: IssueStore | None = None) -> None:
        self.config = config
        self.store = store or IssueStore(config.state_dir)
        self.store.bind({"repository": config.repository, "github_api": config.github_api, "jira_url": config.jira_url})
        self.providers = providers if providers is not None else self._providers()

    def _providers(self) -> dict[str, Any]:
        providers: dict[str, Any] = {"github": GitHubIssues(self.config)}
        if self.config.jira_url:
            providers["jira"] = JiraIssues(self.config)
        return providers

    def close(self) -> None:
        """Close all provider connections."""
        for provider in self.providers.values():
            provider.close()

    def discover(self, dry_run: bool = False) -> list[dict[str, Any]]:
        """Read all source pages; dry-run makes neither queue nor platform changes."""
        snapshots = []
        for provider in self.providers.values():
            for snapshot in provider.scan():
                if snapshot.eligible(provider.bot):
                    snapshots.append(snapshot)
        snapshots.sort(key=lambda item: item.key)
        results = []
        for snapshot in snapshots:
            inserted = False if dry_run else self.store.enqueue(snapshot)
            results.append({"key": snapshot.key, "title": snapshot.title, "queued": inserted})
        return results

    def _fetch(self, key: str) -> tuple[Any, IssueSnapshot]:
        source, separator, external_id = key.partition(":")
        if not separator or source not in self.providers:
            raise IssueWorkerError("issue key must name a configured source: github:123 or jira:PROJECT-123")
        provider = self.providers[source]
        return provider, provider.fetch(external_id)

    def enqueue(self, key: str) -> bool:
        """Queue one eligible issue without giving MCP callers configuration authority."""
        provider, snapshot = self._fetch(key)
        if not snapshot.eligible(provider.bot):
            raise IssueWorkerError("issue must be open, unassigned and labeled automation-ready")
        return self.store.enqueue(snapshot)

    def retry(self, key: str) -> None:
        """Requeue a terminal issue only after an operator restores its ready label."""
        provider, snapshot = self._fetch(key)
        if not snapshot.eligible(provider.bot, resume=True):
            raise IssueWorkerError("retry requires an open issue with automation-ready and no different owner")
        with self.store.lease():
            previous = self.store.status(key)
            branch = previous[0]["data"].get("branch") if previous else None
            if branch:
                github = self.providers["github"]
                owner = self.config.repository.split("/")[0]
                opened = github.client.request("GET", github.prefix + "/pulls", params={
                    "head": owner + ":" + branch, "base": self.config.base_branch, "state": "open",
                })
                if opened:
                    raise IssueWorkerError("an earlier run has an open PR; review or close it before retry")
            self.store.retry(snapshot)
