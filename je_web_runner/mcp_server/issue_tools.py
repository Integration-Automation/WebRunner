"""Host-configured issue queue tools; long-running coding stays in the worker process."""
from __future__ import annotations

import os
from functools import partial
from pathlib import Path
from typing import Any

from je_web_runner.mcp_server._types import READ_ONLY, Tool
from je_web_runner.utils.issue_worker import IssueInbox, IssueStore, IssueWorkerConfig, IssueWorkerError
from je_web_runner.utils.issue_worker.metrics import IssueMetrics


def _host_configuration() -> tuple[IssueWorkerConfig | None, str]:
    path = os.environ.get("WEBRUNNER_ISSUE_CONFIG")
    if not path:
        return None, "set WEBRUNNER_ISSUE_CONFIG on the server host to enable issue queue tools"
    try:
        return IssueWorkerConfig.load(path), ""
    except (OSError, ValueError, IssueWorkerError):
        return None, "invalid host issue configuration; fix it and restart the MCP server"


def _status(arguments: dict[str, Any], config: IssueWorkerConfig | None, error: str) -> Any:
    if config is None:
        raise IssueWorkerError(error)
    if not (Path(config.state_dir) / "issues.sqlite3").exists():
        return {"jobs": []}
    store = IssueStore(config.state_dir)
    store.bind({"repository": config.repository, "github_api": config.github_api, "jira_url": config.jira_url})
    return {"jobs": store.status(arguments.get("issue"))}


def _enqueue(arguments: dict[str, Any], config: IssueWorkerConfig | None, error: str) -> Any:
    if config is None:
        raise IssueWorkerError(error)
    inbox = IssueInbox(config)
    try:
        inserted = inbox.enqueue(arguments["issue"])
        return {"issue": arguments["issue"], "queued": inserted,
                "message": "The configured local worker consumes this queue; this tool does not start coding."}
    finally:
        inbox.close()


def _metrics(arguments: dict[str, Any], config: IssueWorkerConfig | None, error: str) -> Any:
    if config is None:
        raise IssueWorkerError(error)
    store = IssueStore(config.state_dir)
    store.bind({"repository": config.repository, "github_api": config.github_api, "jira_url": config.jira_url})
    return IssueMetrics(store).summary(arguments.get("since_hours"), arguments.get("issue"))


def build_issue_tools() -> list[Tool]:
    """Expose queue/status/local metrics, never config overrides or arbitrary commands."""
    config, error = _host_configuration()
    issue = {"type": "string", "description": "Configured source issue key: github:123 or jira:PROJECT-123."}
    metrics_properties = {"issue": issue, "since_hours": {
        "type": "number", "exclusiveMinimum": 0,
        "description": "Optional positive recorded-history window in hours."}}
    return [
        Tool(name="webrunner_issue_metrics", title="Inspect local issue delivery metrics",
             description="Read local delivery outcomes, holds and failures; business acceptance is not measured.",
             input_schema={"type": "object", "properties": metrics_properties, "additionalProperties": False},
             annotations=READ_ONLY, handler=partial(_metrics, config=config, error=error)),
        Tool(name="webrunner_issue_status", title="Inspect local issue jobs",
             description="Read saved issue job status.",
             input_schema={"type": "object", "properties": {"issue": issue}, "additionalProperties": False},
             annotations=READ_ONLY, handler=partial(_status, config=config, error=error)),
        Tool(name="webrunner_issue_enqueue", title="Queue an eligible issue", description=(
            "Queue an open unassigned issue already labeled automation-ready, using host configuration only. "
            "A separately started local worker handles coding and reviewed PR delivery."),
             input_schema={"type": "object", "properties": {"issue": issue}, "required": ["issue"],
                           "additionalProperties": False},
             annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True,
                          "openWorldHint": True}, handler=partial(_enqueue, config=config, error=error)),
    ]
