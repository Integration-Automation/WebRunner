"""GitHub and Jira Cloud adapters for ready issues and idempotent progress reporting."""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any, Iterable
from urllib.parse import quote

from requests.auth import HTTPBasicAuth
from je_web_runner.utils.agent.runner import Redactor

from je_web_runner.utils.issue_worker.http import PlatformClient
from je_web_runner.utils.issue_worker.types import IssueSnapshot, IssueWorkerConfig, IssueWorkerError

MANAGED = {"automation-running", "automation-review", "automation-needs-info",
           "automation-failed", "automation-cancelled"}
LABELS = {"awaiting_review": "automation-review", "needs_info": "automation-needs-info",
          "failed": "automation-failed", "cancelled": "automation-cancelled"}


def safe_snapshot(snapshot: IssueSnapshot, config: IssueWorkerConfig) -> IssueSnapshot:
    """Keep host credentials out of persistent requirements and model context."""
    redactor = Redactor()
    redactor.secrets.update(os.environ[name] for name in (config.github_token_env, config.jira_token_env)
                            if os.environ.get(name))
    return replace(snapshot, title=redactor.clean(snapshot.title), body=redactor.clean(snapshot.body),
                   url=redactor.clean(snapshot.url))


def adf_text(value: Any) -> str:
    """Extract plain requirement text from Atlassian Document Format."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (adf_text(item) for item in value)))
    if isinstance(value, dict):
        return value.get("text", "") + adf_text(value.get("content", []))
    return ""


def adf_document(text: str) -> dict[str, Any]:
    """Encode a progress comment using Jira REST v3's document format."""
    return {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": text}]},
    ]}


class GitHubIssues:
    """GitHub source scoped to the host-configured WebRunner repository."""

    source = "github"

    def __init__(self, config: IssueWorkerConfig, client: PlatformClient | None = None) -> None:
        self.config = config
        self.bot = config.github_bot
        self.client = client or PlatformClient(config.github_api)
        self.prefix = f"/repos/{config.repository}"
        self.token = os.environ.get(config.github_token_env, "")
        if self.token:
            self.client.session.headers["Authorization"] = "Bearer " + self.token
        self.client.session.headers["Accept"] = "application/vnd.github+json"
        self._identity_checked = False

    def close(self) -> None:
        """Release platform connections."""
        self.client.close()

    def authorize(self) -> None:
        """Before any write, verify the token belongs to the configured actor."""
        if self._identity_checked:
            return
        if not self.token:
            raise IssueWorkerError("GitHub writes require the configured token environment variable")
        identity = self.client.request("GET", "/user")
        if identity.get("login", "").casefold() != self.bot.casefold():
            raise IssueWorkerError("GitHub token identity does not match github_bot")
        self._identity_checked = True

    def _pages(self, path: str, params: dict[str, Any] | None = None) -> Iterable[dict[str, Any]]:
        page = 1
        while True:
            rows = self.client.request("GET", path, params={**(params or {}), "per_page": 100, "page": page})
            yield from rows
            if len(rows) < 100:
                return
            page += 1

    def scan(self) -> Iterable[IssueSnapshot]:
        """List all eligible pages, excluding PRs returned by the issues endpoint."""
        for item in self._pages(self.prefix + "/issues", {"state": "open", "labels": "automation-ready"}):
            if "pull_request" not in item and not item.get("assignees"):
                snapshot = self.fetch(str(item["number"]))
                if snapshot.eligible(self.bot):
                    yield snapshot

    def fetch(self, external_id: str) -> IssueSnapshot:
        """Read an issue and up to its last twenty human comments as requirements."""
        IssueSnapshot("github", external_id, "", "", "")
        path = self.prefix + "/issues/" + external_id
        item = self.client.request("GET", path)
        if "pull_request" in item:
            raise IssueWorkerError("pull requests are not eligible issues")
        comments = [row.get("body", "") for row in self._pages(path + "/comments")
                    if row.get("user", {}).get("login", "").casefold() != self.bot.casefold()]
        owners = [row["login"] for row in item.get("assignees", [])]
        return safe_snapshot(IssueSnapshot(
            "github", external_id, item["title"], (item.get("body") or "") + "\n" + "\n".join(comments[-20:]),
            item["html_url"], tuple(row["name"] for row in item.get("labels", [])),
            ",".join(owners), item["state"] != "open",
        ), self.config)

    def claim(self, snapshot: IssueSnapshot) -> IssueSnapshot:
        """Assign the bot, add only our label, then re-read ownership and requirements."""
        self.authorize()
        current = self.fetch(snapshot.external_id)
        if not current.eligible(self.bot, resume=True) or current.revision != snapshot.revision:
            raise IssueWorkerError("issue eligibility or requirements changed before claim")
        path = self.prefix + "/issues/" + snapshot.external_id
        self.client.request("POST", path + "/assignees", payload={"assignees": [self.bot]})
        self.client.request("POST", path + "/labels", payload={"labels": ["automation-running"]})
        return self.fetch(snapshot.external_id)

    def report(self, snapshot: IssueSnapshot, status: str, message: str) -> None:
        """Update one bot-owned progress comment and only managed labels."""
        self.authorize()
        current = self.fetch(snapshot.external_id)
        path = self.prefix + "/issues/" + snapshot.external_id
        marker = f"<!-- webrunner-issue:{snapshot.key} -->"
        payload = {"body": marker + "\n" + message}
        comments = list(self._pages(path + "/comments"))
        existing = next((row for row in comments if marker in (row.get("body") or "")
                         and row.get("user", {}).get("login", "").casefold() == self.bot.casefold()), None)
        if existing:
            self.client.request("PATCH", self.prefix + f"/issues/comments/{existing['id']}", payload=payload)
        else:
            self.client.request("POST", path + "/comments", payload=payload)
        if current.assignee != self.bot or current.closed:
            return
        target = LABELS.get(status, "automation-running")
        for label in set(current.labels) & (MANAGED - {target}):
            self.client.request("DELETE", path + "/labels/" + quote(label, safe=""), missing_ok=True)
        self.client.request("POST", path + "/labels", payload={"labels": [target]})
        if status in LABELS and "automation-ready" in current.labels:
            self.client.request("DELETE", path + "/labels/automation-ready", missing_ok=True)


class JiraIssues:
    """Jira Cloud source; workflow status names are deliberately not assumed."""

    source = "jira"

    def __init__(self, config: IssueWorkerConfig, client: PlatformClient | None = None) -> None:
        self.config = config
        self.bot = config.jira_bot
        self.client = client or PlatformClient(config.jira_url)
        self.email = os.environ.get(config.jira_email_env, "")
        self.token = os.environ.get(config.jira_token_env, "")
        self.client.session.auth = HTTPBasicAuth(self.email, self.token)
        self._identity_checked = False

    def close(self) -> None:
        """Release platform connections."""
        self.client.close()

    def authorize(self) -> None:
        """Verify the configured Jira account before writing progress or ownership."""
        if self._identity_checked:
            return
        if not self.email or not self.token:
            raise IssueWorkerError("Jira requires its configured email and API token environment variables")
        if self.client.request("GET", "/rest/api/3/myself").get("accountId") != self.bot:
            raise IssueWorkerError("Jira token identity does not match jira_bot")
        self._identity_checked = True

    def scan(self) -> Iterable[IssueSnapshot]:
        """Use enhanced JQL search and its nextPageToken, never the retired search endpoint."""
        projects = ",".join(self.config.jira_projects)
        jql = f"project in ({projects}) AND labels = automation-ready AND assignee is EMPTY AND statusCategory != Done"
        payload: dict[str, Any] = {"jql": jql, "maxResults": 100, "fields": ["summary"]}
        while True:
            data = self.client.request("POST", "/rest/api/3/search/jql", payload=payload)
            for row in data.get("issues", []):
                snapshot = self.fetch(row["key"])
                if snapshot.eligible(self.bot):
                    yield snapshot
            token = data.get("nextPageToken")
            if not token or data.get("isLast"):
                return
            if token == payload.get("nextPageToken"):
                raise IssueWorkerError("Jira repeated its search page token")
            payload["nextPageToken"] = token

    def fetch(self, external_id: str) -> IssueSnapshot:
        """Normalize ADF description and recent human comments."""
        IssueSnapshot("jira", external_id, "", "", "")
        if external_id.rsplit("-", 1)[0] not in self.config.jira_projects:
            raise IssueWorkerError("Jira issue is outside the project allowlist")
        path = "/rest/api/3/issue/" + external_id
        item = self.client.request("GET", path)
        comments = self.client.request("GET", path + "/comment", params={"orderBy": "-created", "maxResults": 20})
        human = [adf_text(row.get("body")) for row in reversed(comments.get("comments", []))
                 if row.get("author", {}).get("accountId") != self.bot]
        fields = item["fields"]
        return safe_snapshot(IssueSnapshot(
            "jira", external_id, fields["summary"], adf_text(fields.get("description")) + "\n" + "\n".join(human),
            self.config.jira_url + "/browse/" + external_id, tuple(fields.get("labels", [])),
            (fields.get("assignee") or {}).get("accountId", ""),
            fields.get("status", {}).get("statusCategory", {}).get("key") == "done",
            fields.get("issuetype", {}).get("name", "development"),
        ), self.config)

    def claim(self, snapshot: IssueSnapshot) -> IssueSnapshot:
        """Assign our account and append a progress label without replacing human labels."""
        self.authorize()
        current = self.fetch(snapshot.external_id)
        if not current.eligible(self.bot, resume=True) or current.revision != snapshot.revision:
            raise IssueWorkerError("issue eligibility or requirements changed before claim")
        self.client.request("PUT", "/rest/api/3/issue/" + snapshot.external_id, payload={
            "fields": {"assignee": {"accountId": self.bot}},
            "update": {"labels": [{"add": "automation-running"}]},
        })
        return self.fetch(snapshot.external_id)

    def report(self, snapshot: IssueSnapshot, status: str, message: str) -> None:
        """Update one bot-owned comment with Jira's paginated comment API."""
        self.authorize()
        current = self.fetch(snapshot.external_id)
        path = "/rest/api/3/issue/" + snapshot.external_id
        marker = f"[webrunner-issue:{snapshot.key}]"
        rows = self._comments(path)
        existing = next((row for row in rows if marker in adf_text(row.get("body"))
                         and row.get("author", {}).get("accountId") == self.bot), None)
        payload = {"body": adf_document(marker + "\n" + message)}
        if existing:
            self.client.request("PUT", path + f"/comment/{existing['id']}", payload=payload)
        else:
            self.client.request("POST", path + "/comment", payload=payload)
        if current.assignee == self.bot and not current.closed:
            target = LABELS.get(status, "automation-running")
            remove = set(current.labels) & (MANAGED - {target})
            if status in LABELS:
                remove |= set(current.labels) & {"automation-ready"}
            updates = [{"remove": label} for label in sorted(remove)] + [{"add": target}]
            self.client.request("PUT", path, payload={"update": {"labels": updates}})

    def _comments(self, path: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        while True:
            page = self.client.request("GET", path + "/comment", params={"startAt": len(rows), "maxResults": 100})
            batch = page.get("comments", [])
            rows.extend(batch)
            if not batch or len(rows) >= page.get("total", len(rows)):
                return rows
