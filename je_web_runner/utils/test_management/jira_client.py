"""
JIRA Cloud REST API 整合：建立 issue 與將失敗自動回報。
JIRA Cloud REST API integration: create issues and post run failures.

認證：使用者 email + API token；以 ``HTTPBasicAuth`` 帶入。
Auth: user email + API token via HTTP basic auth.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance


class JiraError(WebRunnerException):
    """Raised when a JIRA API call fails."""


_DEFAULT_TIMEOUT = 30
_NO_EXCEPTION = "None"


def _check_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url:
        raise JiraError("base_url must be a non-empty string")
    if not (base_url.startswith("http://") or base_url.startswith("https://")):  # NOSONAR — scheme allow-list, not an outbound HTTP call
        raise JiraError(f"base_url must be http(s): {base_url!r}")
    return base_url.rstrip("/")


def jira_create_issue(
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    summary: str,
    description: str = "",
    issue_type: str = "Bug",
    extra_fields: Optional[Dict[str, Any]] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    建立 JIRA issue
    Create a JIRA issue and return the response JSON.
    """
    web_runner_logger.info(f"jira_create_issue: project={project_key}")
    url = f"{_check_url(base_url)}/rest/api/3/issue"
    fields: Dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
        "description": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": description}],
                }
            ],
        },
    }
    if extra_fields:
        fields.update(extra_fields)
    response = requests.post(
        url,
        json={"fields": fields},
        auth=HTTPBasicAuth(email, api_token),
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise JiraError(f"JIRA returned {response.status_code}: {response.text[:200]}")
    return response.json()


def jira_create_failure_issues(
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    issue_type: str = "Bug",
    build_url: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    對 ``test_record_instance`` 內每個失敗紀錄建立一個 issue
    Create one issue per failure entry in ``test_record_instance``.
    """
    failures = [
        record for record in test_record_instance.test_record_list
        if record.get("program_exception", _NO_EXCEPTION) != _NO_EXCEPTION
    ]
    issues: List[Dict[str, Any]] = []
    for failure in failures:
        summary = f"WebRunner failure: {failure.get('function_name')}"
        description = (
            f"function: {failure.get('function_name')}\n"
            f"params: {failure.get('local_param')}\n"
            f"time: {failure.get('time')}\n"
            f"exception: {failure.get('program_exception')}\n"
        )
        if build_url:
            description += f"build: {build_url}\n"
        issues.append(jira_create_issue(
            base_url=base_url,
            email=email,
            api_token=api_token,
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
        ))
    return issues
