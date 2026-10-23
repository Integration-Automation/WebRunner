"""Local HTTP platforms/model plus real git and pytest, without contacting external services."""
from __future__ import annotations

import hashlib
from dataclasses import asdict
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from je_web_runner.utils.issue_worker.processor import CodeProcessor
from je_web_runner.utils.issue_worker.providers import adf_document
from je_web_runner.utils.issue_worker.types import IssueWorkerConfig
from je_web_runner.utils.issue_worker.worker import IssueWorker
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace, git_run

_PATCH = """diff --git a/je_web_runner/calc.py b/je_web_runner/calc.py
--- a/je_web_runner/calc.py
+++ b/je_web_runner/calc.py
@@ -1,2 +1,2 @@
 def value():
-    return 1
+    return 2
"""


class FixtureAPI:
    """Small HTTP model of exactly the public endpoints used by the worker."""

    def __init__(self, source, base_sha, base_tree):
        self.source = source
        self.base_sha = base_sha
        self.base_tree = base_tree
        self.validated_tree = ""
        self.labels = {"automation-ready"}
        self.owner = ""
        self.comments = []
        self.refs = {}
        self.prs = []
        self.model_calls = 0
        self.lose_pr_reply = False
        self.pr_posts = 0
        self.checks = []
        self.requests = []
        self.url = ""

    def get(self, path, query):
        if path == "/api/status":
            return {"cloud": {"disabled": True}}
        if path == "/api/tags":
            return {"models": [{"name": "fixture-local:latest"}]}
        if path == "/user":
            return {"login": "worker-bot"}
        if path == "/rest/api/3/myself":
            return {"accountId": "jira-bot"}
        if path.startswith("/rest/api/3/issue/"):
            return self._jira_get(path)
        return self._github_get(path, query)

    def _jira_get(self, path):
        if path.endswith("/comment"):
            return {"comments": self.comments, "total": len(self.comments)}
        return {"key": "WR-12", "fields": {
            "summary": "Fix value", "description": adf_document("value() must return two; the failing test proves it."),
            "labels": sorted(self.labels), "assignee": {"accountId": self.owner} if self.owner else None,
            "status": {"statusCategory": {"key": "new"}}, "issuetype": {"name": "Bug"},
        }}

    def _github_get(self, path, query):
        if path.endswith("/pulls"):
            branch = query["head"][0].split(":", 1)[1]
            return [row for row in self.prs if row["head"]["ref"] == branch]
        if "/git/commits/" in path:
            return {"tree": {"sha": self.base_tree}}
        if "/git/ref/heads/" in path:
            branch = path.split("/git/ref/heads/", 1)[1]
            sha = self.base_sha if branch == "dev" else self.refs.get(branch)
            return {"object": {"sha": sha}} if sha else None
        if path.endswith("/comments"):
            return self.comments
        issue = {"number": 12, "title": "Fix value", "body": "value() must return two; the failing test proves it.",
                 "html_url": self.url + "/issues/12", "state": "open",
                 "labels": [{"name": value} for value in sorted(self.labels)],
                 "assignees": [{"login": self.owner}] if self.owner else []}
        if path.endswith("/issues"):
            return [issue] if self.source == "github" and not self.owner and "automation-ready" in self.labels else []
        return issue

    def mutate(self, method, path, data):
        if path == "/api/chat":
            action = {"kind": "patch", "text": _PATCH} if self.model_calls == 0 else {
                "kind": "finish", "summary": "Corrected value(); baseline failed and final tests passed.",
            }
            self.model_calls += 1
            return 200, {"message": {"content": json.dumps(action)}}
        if path == "/rest/api/3/search/jql":
            rows = [{"key": "WR-12"}] if self.source == "jira" and not self.owner else []
            return 200, {"issues": rows, "isLast": True}
        if path.startswith("/rest/api/3/issue/"):
            return self._jira_write(method, path, data)
        if "/git/" in path or path.endswith("/pulls"):
            return self._publish(path, data)
        return self._github_write(method, path, data)

    def _github_write(self, method, path, data):
        if path.endswith("/assignees"):
            self.owner = data["assignees"][0]
        elif "/labels/" in path and method == "DELETE":
            self.labels.discard(path.rsplit("/", 1)[1])
            return 204, None
        elif path.endswith("/labels"):
            self.labels.update(data["labels"])
        elif method == "PATCH":
            self.comments[0]["body"] = data["body"]
        elif path.endswith("/comments"):
            self.comments.append({"id": 1, "body": data["body"], "user": {"login": "worker-bot"}})
        else:
            raise AssertionError((method, path))
        return 200, {}

    def _jira_write(self, method, path, data):
        if "/comment" in path:
            row = {"id": "1", "body": data["body"], "author": {"accountId": "jira-bot"}}
            if method == "PUT":
                self.comments[0] = row
            else:
                self.comments.append(row)
            return 200, row
        if "fields" in data:
            self.owner = data["fields"]["assignee"]["accountId"]
        for change in data.get("update", {}).get("labels", []):
            if "add" in change:
                self.labels.add(change["add"])
            else:
                self.labels.discard(change["remove"])
        return 204, None

    def _publish(self, path, data):
        if path.endswith("/git/trees"):
            assert data["base_tree"] == self.base_tree
            assert data["tree"] == [{"path": "je_web_runner/calc.py", "mode": "100644", "type": "blob",
                                     "content": "def value():\n    return 2\n"}]
            return 201, {"sha": self.validated_tree}
        if path.endswith("/git/commits"):
            return 201, {"sha": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:40]}
        if path.endswith("/git/refs"):
            self.refs[data["ref"].removeprefix("refs/heads/")] = data["sha"]
            return 201, {}
        self.pr_posts += 1
        row = {"number": 40, "html_url": self.url + "/pull/40", "state": "open", "body": data["body"],
               "user": {"login": "worker-bot"}, "head": {"ref": data["head"], "sha": self.refs[data["head"]]}}
        self.prs.append(row)
        if self.lose_pr_reply:
            self.lose_pr_reply = False
            return 503, {"error": "reply lost after successful creation"}
        return 201, row


@pytest.fixture
def pipeline(tmp_path, request, monkeypatch):
    original = tmp_path / "source"
    (original / "je_web_runner").mkdir(parents=True)
    (original / "test").mkdir()
    (original / "je_web_runner/__init__.py").write_text("", newline="\n")
    (original / "je_web_runner/calc.py").write_text("def value():\n    return 1\n", newline="\n")
    (original / "test/test_calc.py").write_text(
        "from je_web_runner.calc import value\ndef test_value():\n    assert value() == 2\n", newline="\n")
    git_run(original, ["init", "-b", "dev"])
    git_run(original, ["add", "--", "je_web_runner", "test"])
    git_run(original, ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-m", "Baseline"])
    source = getattr(request, "param", "github")
    api = FixtureAPI(source, git_run(original, ["rev-parse", "HEAD"]).strip(),
                     git_run(original, ["rev-parse", "HEAD^{tree}"]).strip())
    server = _serve(api)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api.url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setenv("FIXTURE_GH_TOKEN", "fixture-github-secret")
    monkeypatch.setenv("FIXTURE_JIRA_TOKEN", "fixture-jira-secret")
    monkeypatch.setenv("FIXTURE_JIRA_EMAIL", "fixture@example.test")
    config = IssueWorkerConfig(str(tmp_path / "state"), "fixture-local", "worker-bot", github_api=api.url,
                               github_token_env="FIXTURE_GH_TOKEN", ollama_url=api.url,
                               checks={"unit": ["python", "-m", "pytest", "test", "-q"]})
    if source == "jira":
        config.jira_url, config.jira_projects, config.jira_bot = api.url, ["WR"], "jira-bot"
        config.jira_token_env, config.jira_email_env = "FIXTURE_JIRA_TOKEN", "FIXTURE_JIRA_EMAIL"
    processor = CodeProcessor(config, sandbox=FixtureSandbox(api))
    worker = IssueWorker(config, processor=processor,
                         workspace_factory=lambda settings, job: IssueWorkspace.prepare(settings, job, str(original)))
    try:
        yield worker, api, original
    finally:
        worker.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _serve(api):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond("GET")

        def do_POST(self):
            self.respond("POST")

        def do_PUT(self):
            self.respond("PUT")

        def do_PATCH(self):
            self.respond("PATCH")

        def do_DELETE(self):
            self.respond("DELETE")

        def respond(self, method):
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            api.requests.append((method, path, self.headers.get("Authorization")))
            if method == "GET":
                payload = api.get(path, parse_qs(parsed.query))
                status = 404 if payload is None else 200
            else:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or "null")
                status, payload = api.mutate(method, path, data)
            body = json.dumps(payload).encode() if payload is not None else b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


class FixtureSandbox:
    """Trusted fixture-only executor: real pytest evidence, separate from Podman policy tests."""

    def __init__(self, api):
        self.api = api

    def preflight(self):
        return

    def check(self, workspace, name, timeout):
        with tempfile.TemporaryDirectory(prefix="issue-pipeline-test-") as temporary:
            source = Path(temporary) / "source"
            workspace.export(source)
            env = {key: value for key, value in os.environ.items()
                   if key.upper() in {"PATH", "SYSTEMROOT", "TEMP", "TMP"}}
            env.update({"PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"})
            result = subprocess.run([sys.executable, "-m", "pytest", "test", "-q", "-p", "no:cacheprovider"],
                                    cwd=source, env=env, capture_output=True, text=True,
                                    timeout=min(20, timeout), check=False)
        tree = workspace.fingerprint()
        self.api.validated_tree = tree
        self.api.checks.append(result.returncode)
        return {"name": name, "passed": result.returncode == 0, "tree": tree,
                "output": result.stdout[-4000:] + result.stderr[-1000:]}


@pytest.mark.parametrize("pipeline", ["github", "jira"], indirect=True)
def test_ready_issue_to_single_reviewed_pr_with_real_regression_evidence(pipeline):
    worker, api, original = pipeline
    preview = worker.run_once(dry_run=True)
    assert len(preview["preview"]) == 1
    assert api.owner == "" and api.model_calls == 0
    result = worker.run_once()
    assert result["status"] == "awaiting_review", result
    assert api.checks == [1, 0]  # real failing baseline, real passing patched test
    assert api.model_calls == 2 and len(api.prs) == 1
    assert api.pr_posts == 1
    assert "automation-review" in api.labels and "automation-ready" not in api.labels
    assert len(api.comments) == 1
    assert "return 1" in (original / "je_web_runner/calc.py").read_text()
    assert worker.run_once()["status"] == "idle"
    encoded = json.dumps(worker.status())
    assert "fixture-github-secret" not in encoded and "fixture-jira-secret" not in encoded
    assert all(auth is None for _method, path, auth in api.requests if path.startswith("/api/"))


def test_lost_pr_reply_recovers_without_second_pr_or_model_run(pipeline):
    worker, api, _original = pipeline
    api.lose_pr_reply = True
    uncertain = worker.run_once()
    assert uncertain["status"] == "publishing", uncertain
    assert len(api.prs) == 1
    worker.store.save(uncertain["key"], uncertain["status"], uncertain["data"])
    recovered = worker.run_once(discover=False)
    assert recovered["status"] == "awaiting_review", recovered
    assert api.pr_posts == 1 and api.model_calls == 2
    assert recovered["data"]["report_pending"] is False


def test_cli_preview_uses_platform_reads_without_claiming_or_running_a_model(pipeline, tmp_path):
    worker, api, _original = pipeline
    config = tmp_path / "worker.json"
    config.write_text(json.dumps(asdict(worker.config)), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", WEBRUNNER_LOG_PATH=str(tmp_path / "preview.log"))
    result = subprocess.run([sys.executable, "-m", "je_web_runner.issue_worker", "run", "--config", str(config),
                             "--dry-run"], capture_output=True, text=True, encoding="utf-8", env=env,
                            timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["preview"]) == 1
    assert api.owner == "" and api.model_calls == 0
    assert worker.status() == []
