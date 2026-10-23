"""Local HTTP platforms/model plus real git and pytest, without contacting external services."""
from __future__ import annotations

from dataclasses import asdict
import ast
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from unittest.mock import patch

import pytest

from je_web_runner.utils.issue_worker.processor import CodeProcessor
from je_web_runner.utils.issue_worker.publisher import GitHubPublisher
from je_web_runner.utils.issue_worker.providers import adf_document
from je_web_runner.utils.issue_worker.sandbox import PodmanSandbox
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
        self.expected_entries = None
        self.read_status = 200
        self.git_root = None
        self.original = None
        self.reviews, self.review_comments, self.pr_comments = [], [], []
        self.model_actions = None
        self.lose_ref_reply = False
        self.labels = {"automation-ready"}
        self.owner = ""
        self.comments = []
        self.refs = {}
        self.prs = []
        self.model_calls = 0
        self.coding_calls = 0
        self.requirement_reply = {"summary": "Fix return value", "kind": "bug", "questions": [], "criteria": [
            {"id": "C1", "description": "value() returns two", "checks": ["unit"], "browser": [], "manual": False}]}
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
        feedback = {
            "/pulls/40": self.prs[0] if self.prs else None,
            "/pulls/40/reviews": self.reviews,
            "/pulls/40/comments": self.review_comments,
            "/issues/40/comments": self.pr_comments,
            "/permission": {"permission": "write"},
            "/check-runs": {"check_runs": []},
            "/statuses": [],
        }
        for suffix, response in feedback.items():
            if path.endswith(suffix):
                return response
        if path.endswith("/pulls"):
            branch = query["head"][0].split(":", 1)[1]
            return [row for row in self.prs if row["head"]["ref"] == branch]
        if "/git/commits/" in path:
            tree = git_run(self.git_root, ["rev-parse", path.rsplit("/", 1)[-1] + "^{tree}"]).strip()
            return {"tree": {"sha": tree}}
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
            self.model_calls += 1
            if "criteria" in data.get("format", {}).get("properties", {}):
                return 200, {"message": {"content": json.dumps(self.requirement_reply)}}
            action = {"kind": "patch", "text": _PATCH} if self.coding_calls == 0 else {
                "kind": "finish", "summary": "Corrected value(); baseline failed and final tests passed.",
            }
            if self.model_actions is not None:
                action = self.model_actions[self.coding_calls]
            self.coding_calls += 1
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
        if path.endswith("/issues/40/comments"):
            row = {"id": 2, "body": data["body"], "user": {"login": "worker-bot"}}
            self.pr_comments.append(row)
            return 201, row
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
            assert data["base_tree"] == git_run(self.git_root, ["rev-parse", "HEAD^{tree}"]).strip()
            expected = self.expected_entries if self.expected_entries is not None else [
                {"path": "je_web_runner/calc.py", "mode": "100644", "type": "blob",
                 "content": "def value():\n    return 2\n"}]
            assert data["tree"] == expected
            return 201, {"sha": self.validated_tree}
        if path.endswith("/git/commits"):
            args = ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit-tree", data["tree"]]
            for parent in data["parents"]:
                args.extend(["-p", parent])
            return 201, {"sha": git_run(self.git_root, [*args, "-m", data["message"]]).strip()}
        if "/git/refs" in path:
            branch = data["ref"].removeprefix("refs/heads/") if "ref" in data else path.split("/heads/", 1)[1]
            if "ref" not in data:
                assert data["force"] is False
            git_run(self.git_root, ["push", str(self.original), data["sha"] + ":refs/heads/" + branch])
            self.refs[branch] = data["sha"]
            for row in self.prs:
                if row["head"]["ref"] == branch:
                    row["head"]["sha"] = data["sha"]
            if self.lose_ref_reply:
                self.lose_ref_reply = False
                return 503, {"error": "reference reply lost"}
            return 201, {}
        self.pr_posts += 1
        row = {"number": 40, "html_url": self.url + "/pull/40", "state": "open", "body": data["body"],
               "user": {"login": "worker-bot"}, "head": {"ref": data["head"], "sha": self.refs[data["head"]],
               "repo": {"full_name": "Integration-Automation/WebRunner"}},
               "base": {"ref": "dev", "repo": {"full_name": "Integration-Automation/WebRunner"}}}
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
    scenario = getattr(request, "param", "github")
    real = isinstance(scenario, dict)
    source = scenario["source"] if real else scenario
    if real and os.environ.get("WEBRUNNER_ISSUE_REAL_TESTS") != "1":
        pytest.skip("run scripts/verify_issue_worker.py for required real model/container acceptance")
    if real and not all(os.environ.get(name) for name in ("WEBRUNNER_ISSUE_MODEL", "WEBRUNNER_ISSUE_IMAGE")):
        pytest.fail("real acceptance requires WEBRUNNER_ISSUE_MODEL and WEBRUNNER_ISSUE_IMAGE")
    api = FixtureAPI(source, git_run(original, ["rev-parse", "HEAD"]).strip(),
                     git_run(original, ["rev-parse", "HEAD^{tree}"]).strip())
    api.original = original
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
    if real:
        config.model, config.image = os.environ["WEBRUNNER_ISSUE_MODEL"], os.environ["WEBRUNNER_ISSUE_IMAGE"]
        config.ollama_url = os.environ.get("WEBRUNNER_ISSUE_OLLAMA_URL", "http://127.0.0.1:11434")
        config.timeout, config.max_tools = 600, 20
        config.requirements_enabled = True
    sandbox = RecordingPodmanSandbox(config, api) if real else FixtureSandbox(api)
    processor = CodeProcessor(config, sandbox=sandbox)
    worker = IssueWorker(config, processor=processor,
                         workspace_factory=lambda settings, job: IssueWorkspace.prepare(settings, job, str(original)))
    try:
        yield worker, api, original
    finally:
        worker.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class FixtureHandler(BaseHTTPRequestHandler):
    """HTTP fixture adapter, including bounded connection failure injection."""
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
        api = self.server.api
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        api.requests.append((method, path, self.headers.get("Authorization")))
        if method == "GET":
            payload = api.get(path, parse_qs(parsed.query))
            status = 404 if payload is None else 200
            if path.endswith("/issues") and api.read_status != 200:
                if api.read_status == 0:
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                status, payload = api.read_status, {"error": "injected platform outage"}
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


def _serve(api):
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    server.api = api
    return server


class FixtureSandbox:
    """Trusted fixture-only executor: real pytest evidence, separate from Podman policy tests."""

    def __init__(self, api):
        self.api = api

    def preflight(self):
        return

    def check(self, workspace, name, timeout):
        self.api.git_root = workspace.root
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
        self.api.expected_entries = GitHubPublisher._entries(workspace)
        self.api.checks.append(result.returncode)
        return {"name": name, "passed": result.returncode == 0, "tree": tree,
                "output": result.stdout[-4000:] + result.stderr[-1000:]}


class RecordingPodmanSandbox(PodmanSandbox):
    """Real offline execution; capture the independently validated tree for the fake publisher."""

    def __init__(self, config, api):
        super().__init__(config)
        self.api = api

    def check(self, workspace, name, timeout):
        self.api.git_root = workspace.root
        result = super().check(workspace, name, timeout)
        self.api.validated_tree = result["tree"]
        self.api.expected_entries = GitHubPublisher._entries(workspace)
        self.api.checks.append(0 if result["passed"] else 1)
        return result


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


@pytest.mark.parametrize("pipeline", [{"source": "github"}, {"source": "jira"}], indirect=True)
@pytest.mark.parametrize("lose_reply", [False, True])
def test_real_runtime_model_container_and_reviewed_delivery(pipeline, lose_reply):
    worker, api, original = pipeline
    worker.processor.preflight()  # Missing dependencies must fail this selected acceptance test.
    api.lose_pr_reply = lose_reply
    result = worker.run_once()
    if lose_reply:
        assert result["status"] == "publishing", result
        calls = worker.config.max_tools - result["data"]["tool_count"]
        worker.store.save(result["key"], result["status"], result["data"])
        result = worker.run_once(discover=False)
        assert worker.config.max_tools - result["data"]["tool_count"] == calls
    assert result["status"] == "awaiting_review", result
    assert api.checks[0] == 1 and api.checks[-1] == 0
    assert api.pr_posts == 1 and len(api.prs) == 1
    assert api.model_calls == 0  # The fixture model endpoint must never be used here.
    assert "return 1" in (original / "je_web_runner/calc.py").read_text()
    assert "fixture-github-secret" not in json.dumps(worker.status())


@pytest.mark.parametrize("pipeline", [{"source": "github"}, {"source": "jira"}], indirect=True)
def test_real_runtime_review_revises_same_pr_and_recovers_lost_reference(pipeline):
    worker, api, original = pipeline
    worker.processor.preflight()
    worker.config.review_enabled = True
    worker.config.review_poll_seconds = 0.01
    initial = worker.run_once()
    assert initial["status"] == "awaiting_review", initial
    api.reviews = [{"id": 70, "state": "CHANGES_REQUESTED", "commit_id": initial["data"]["pr"]["head"],
                    "body": "Add a nonempty docstring to value(), retaining return value two.",
                    "user": {"login": "maintainer", "type": "User"}}]
    api.lose_ref_reply = True
    uncertain = worker.run_once()
    assert uncertain["status"] == "publishing", uncertain
    worker.store.save(uncertain["key"], uncertain["status"], uncertain["data"])
    recovered = worker.run_once(discover=False)
    assert recovered["status"] == "awaiting_review", recovered
    assert recovered["data"]["review_rounds"] == 1
    assert api.pr_posts == 1 and len(api.pr_comments) == 1
    assert api.model_calls == 0
    assert api.checks[0] == 1 and api.checks[-1] == 0
    code = git_run(api.git_root, ["show", ":je_web_runner/calc.py"])
    function = next(node for node in ast.parse(code).body if isinstance(node, ast.FunctionDef) and node.name == "value")
    assert ast.get_docstring(function)
    assert "return 1" in (original / "je_web_runner/calc.py").read_text()
    assert worker.run_once()["status"] == "idle"


def _observe_soak_health(health, observed, instances, faults):
    """Record actual health observations, independently of the injected fixture status."""
    if health["active"]:
        instances.add(health["instance"])
    error = health.get("error") or ""
    for name, marker in (("429", "rate limit"), ("503", "HTTP 503"), ("disconnect", "connection failed")):
        if marker in error:
            observed.add(name)
    if health.get("last_poll") and not error:
        observed.add("recovered")
    if health["status"] == "stale":
        faults.append("heartbeat expired")


@pytest.mark.parametrize("pipeline", [{"source": "github"}], indirect=True)
def test_real_runtime_watch_soak(pipeline):
    seconds = float(os.environ.get("WEBRUNNER_ISSUE_SOAK_SECONDS", "0"))
    if seconds <= 0:
        pytest.skip("set a soak duration through scripts/verify_issue_worker.py")
    worker, api, _original = pipeline
    worker.processor.preflight()
    result = worker.run_once()
    assert result["status"] == "awaiting_review", result
    worker.config.poll_seconds = 1
    started = time.monotonic()
    deadline = started + seconds
    faults = []
    observed, instances = set(), set()
    finished = threading.Event()

    def monitor():
        # Repeated watch start/stop cycles share durable state; induce rate limits and disconnect responses.
        try:
            next_restart = time.monotonic() + 120
            while not finished.is_set() and time.monotonic() < deadline:
                phase = int(time.monotonic() - started) % 120
                api.read_status = 429 if phase < 10 else (503 if phase < 20 else (0 if phase < 30 else 200))
                health = worker.health()
                _observe_soak_health(health, observed, instances, faults)
                if time.monotonic() >= next_restart and health["active"]:
                    worker.request_stop()
                    next_restart = time.monotonic() + 120
                finished.wait(0.2)
        except Exception as error:
            faults.append(type(error).__name__)
        finally:
            finished.set()
            worker.request_stop()

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    try:
        while not finished.is_set() and time.monotonic() < deadline:
            worker.watch(finished)
    finally:
        finished.set()
        worker.request_stop()
        monitor_thread.join(timeout=5)
    assert faults == []
    report = {"seconds": time.monotonic() - started, "observed": sorted(observed), "instances": len(instances)}
    (Path(worker.config.state_dir) / "soak-evidence.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("SOAK_EVIDENCE=" + json.dumps(report), flush=True)
    assert report["seconds"] >= seconds
    if seconds >= 150:
        assert observed == {"429", "503", "disconnect", "recovered"}, report
        assert len(instances) >= 2, report
    assert len(api.prs) == 1 and api.pr_posts == 1
    assert worker.health()["status"] == "stopped"


def test_watch_recovers_after_rate_limit_and_tcp_disconnect(pipeline):
    worker, api, _original = pipeline
    worker.config.poll_seconds = 0.02
    api.read_status = 429
    stopped = threading.Event()
    faults = []

    def wait_for(predicate):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if predicate():
                return
            stopped.wait(0.01)
        raise AssertionError("worker did not reach the expected recovery checkpoint")

    def monitor():
        try:
            wait_for(lambda: "rate limit" in (worker.health().get("error") or ""))
            api.read_status = 0
            wait_for(lambda: "connection failed" in (worker.health().get("error") or ""))
            api.read_status = 200
            wait_for(lambda: bool(worker.status()) and worker.status()[0]["status"] == "awaiting_review")
        except Exception as error:
            faults.append(str(error))
        finally:
            stopped.set()

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    try:
        with patch("je_web_runner.utils.issue_worker.worker.IssueDoctor") as doctor:
            doctor.return_value.check.return_value = {"ready": True}
            worker.watch(stopped)
    finally:
        stopped.set()
        monitor_thread.join(timeout=5)
    assert faults == []
    assert worker.status()[0]["status"] == "awaiting_review"
    assert api.pr_posts == 1 and len(api.prs) == 1


@pytest.mark.parametrize("pipeline", ["github", "jira"], indirect=True)
def test_review_updates_original_pr_with_real_git_and_tests_and_recovers_lost_ref(pipeline):
    worker, api, original = pipeline
    review_patch = _PATCH.replace("-    return 1", "-    return 2").replace(
        "+    return 2", '+    """Return two for callers."""\n+    return 2'
    ).replace("@@ -1,2 +1,2 @@", "@@ -1,2 +1,3 @@")
    api.model_actions = [{"kind": "patch", "text": _PATCH}, {"kind": "finish", "summary": "Fix return value"},
                         {"kind": "patch", "text": review_patch},
                         {"kind": "finish", "summary": "Document the public value function"}]
    worker.config.review_enabled = True
    worker.config.review_poll_seconds = 0.01
    initial = worker.run_once()
    assert initial["status"] == "awaiting_review", initial
    api.reviews = [{"id": 70, "state": "CHANGES_REQUESTED", "commit_id": initial["data"]["pr"]["head"],
                    "body": "Add a docstring to value(), retaining return value two.",
                    "user": {"login": "maintainer", "type": "User"}}]
    api.lose_ref_reply = True
    uncertain = worker.run_once()
    assert uncertain["status"] == "publishing", uncertain
    assert api.prs[0]["head"]["sha"] != initial["data"]["pr"]["head"]
    worker.store.save(uncertain["key"], uncertain["status"], uncertain["data"])
    recovered = worker.run_once(discover=False)
    assert recovered["status"] == "awaiting_review", recovered
    assert recovered["data"]["review_rounds"] == 1
    assert api.pr_posts == 1 and len(api.pr_comments) == 1
    assert api.model_calls == 4
    assert api.checks == [1, 0, 0, 0]  # baseline/final on initial delivery and revision
    assert "Return two for callers" in git_run(api.git_root, ["show", ":je_web_runner/calc.py"])
    assert "return 1" in (original / "je_web_runner/calc.py").read_text()
    assert worker.run_once()["status"] == "idle"
    assert api.model_calls == 4


@pytest.mark.parametrize("pipeline", ["github", "jira"], indirect=True)
def test_requirement_analysis_produces_tree_bound_evidence_in_the_pr(pipeline):
    worker, api, _original = pipeline
    worker.config.requirements_enabled = True
    result = worker.run_once()
    assert result["status"] == "awaiting_review", result
    evidence = result["data"]["acceptance"]
    assert evidence["tree"] == result["data"]["validated_tree"]
    assert evidence["criteria"][0]["status"] == "evidence_passed"
    assert '"business_verified": false' in api.prs[0]["body"]
    assert api.model_calls == 3 and api.coding_calls == 2


def test_requirement_questions_reach_source_without_coding_or_pr(pipeline):
    worker, api, original = pipeline
    worker.config.requirements_enabled = True
    api.requirement_reply["criteria"] = []
    api.requirement_reply["questions"] = ["Which return value is correct?"]
    result = worker.run_once()
    assert result["status"] == "needs_info", result
    assert api.coding_calls == 0 and api.pr_posts == 0
    assert "Which return" in api.comments[0]["body"]
    assert "return 1" in (original / "je_web_runner/calc.py").read_text()
