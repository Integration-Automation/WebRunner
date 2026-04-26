"""
GitHub PR 留言 bot：跑完自動貼 / 更新 summary 留言。
GitHub PR comment poster. Either creates a new comment on a pull request
or updates the existing WebRunner comment (idempotent via a hidden HTML
marker) so retried CI runs don't pile up.

Auth: pass a token via the ``GITHUB_TOKEN`` env var or the ``token`` arg.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class PrCommentError(WebRunnerException):
    """Raised when posting / updating a PR comment fails."""


_MARKER = "<!-- webrunner-summary -->"


@dataclass
class PrSummary:
    total: int
    passed: int
    failed: int
    skipped: int = 0
    duration_seconds: Optional[float] = None
    flaky: int = 0
    sections: List[Dict[str, Any]] = field(default_factory=list)


def build_summary_markdown(summary: PrSummary, run_url: Optional[str] = None) -> str:
    pass_pct = (summary.passed / summary.total * 100) if summary.total else 0.0
    pieces = [
        _MARKER,
        "## WebRunner test summary",
        "",
        f"- **Total:** {summary.total}",
        f"- **Passed:** {summary.passed} ({pass_pct:.1f}%)",
        f"- **Failed:** {summary.failed}",
        f"- **Skipped:** {summary.skipped}",
    ]
    if summary.flaky:
        pieces.append(f"- **Flaky retries:** {summary.flaky}")
    if summary.duration_seconds is not None:
        pieces.append(f"- **Duration:** {summary.duration_seconds:.1f}s")
    if run_url:
        pieces.append(f"- **Run:** [{run_url}]({run_url})")
    pieces.append("")
    for section in summary.sections:
        title = section.get("title")
        body = section.get("body")
        if title:
            pieces.append(f"### {title}")
        if body:
            pieces.append(str(body))
            pieces.append("")
    return "\n".join(pieces).rstrip() + "\n"


def _request(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> Any:
    if not (url.startswith("https://api.github.com/") or url.startswith("http://api.github.com/")):  # NOSONAR — allow-list
        raise PrCommentError(f"refusing to call non-GitHub URL: {url!r}")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    # Python 3.10+ default context enforces TLS 1.2+. NOSONAR S4423
    ssl_context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(  # nosec B310 — host already validated
            request, timeout=timeout, context=ssl_context,
        ) as response:
            body = response.read().decode("utf-8")
    except (OSError, ValueError) as error:
        raise PrCommentError(f"GitHub call failed: {error!r}") from error
    if not body:
        return None
    try:
        return json.loads(body)
    except ValueError as error:
        raise PrCommentError(f"GitHub returned non-JSON: {error}") from error


def _list_comments(repo: str, pr_number: int, token: str) -> List[Dict[str, Any]]:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    payload = _request("GET", url, token=token)
    if not isinstance(payload, list):
        raise PrCommentError(f"unexpected comments payload: {type(payload).__name__}")
    return payload


def _find_marker(comments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for entry in comments:
        if isinstance(entry, dict) and _MARKER in (entry.get("body") or ""):
            return entry
    return None


def post_or_update_comment(
    repo: str,
    pr_number: int,
    body: str,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    依 marker 判斷新增或覆寫 WebRunner summary 留言
    Find the WebRunner-marker comment on this PR and PATCH it; create a new
    one if no marker comment exists yet.
    """
    used_token = token or os.environ.get("GITHUB_TOKEN")
    if not used_token:
        raise PrCommentError("missing GitHub token (set GITHUB_TOKEN or pass token=)")
    if "/" not in repo:
        raise PrCommentError(f"repo must be 'owner/name': {repo!r}")
    if not isinstance(pr_number, int) or pr_number <= 0:
        raise PrCommentError(f"pr_number must be a positive int: {pr_number!r}")
    if _MARKER not in body:
        body = f"{_MARKER}\n{body}"
    existing = _find_marker(_list_comments(repo, pr_number, used_token))
    if existing is None:
        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        result = _request("POST", url, used_token, payload={"body": body})
        web_runner_logger.info(f"created PR comment id={result.get('id') if result else '?'}")
    else:
        url = f"https://api.github.com/repos/{repo}/issues/comments/{existing['id']}"
        result = _request("PATCH", url, used_token, payload={"body": body})
        web_runner_logger.info(f"updated PR comment id={existing['id']}")
    if not isinstance(result, dict):
        raise PrCommentError(f"unexpected GitHub response: {result!r}")
    return result
