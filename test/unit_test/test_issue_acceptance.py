"""Closed requirement plans, mandatory browser evidence and an immutable trusted verifier boundary."""
import copy
import json
import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from je_web_runner.utils.agent.runner import Redactor
from je_web_runner.utils.issue_worker.browser_acceptance import BrowserAcceptance
from je_web_runner.utils.issue_worker.browser_entry import main as browser_main
from je_web_runner.utils.issue_worker.browser_contract import scenario_task
from je_web_runner.utils.issue_worker.planner import CodeAction, CodingPlanner
from je_web_runner.utils.issue_worker.processor import CodeProcessor
from je_web_runner.utils.issue_worker.publisher import GitHubPublisher
from je_web_runner.utils.issue_worker.requirements import (
    RequirementAnalyzer, RequirementPlan, criterion_evidence, requirement_revision,
)
from je_web_runner.utils.issue_worker.types import IssueWorkerConfig, IssueWorkerError
from test_issue_coding import PATCH


def case():
    return {"server": ["python", "-m", "http.server", "8765", "--bind", "127.0.0.1"], "port": 8765,
            "task": {"goal": "Verify form submission", "start_url": "http://127.0.0.1:8765/index.html",
                     "backend": "selenium", "planner": "steps", "timeout": 10, "action_timeout": 2,
                     "steps": [{"kind": "click", "selector": "#submit"}],
                     "success": [{"kind": "text_contains", "selector": "#result", "value": "Hello"}]}}


def analysis():
    return {"summary": "Correct the return value", "kind": "bug", "questions": [], "criteria": [
        {"id": "C1", "description": "value() returns two", "checks": ["unit"], "browser": [], "manual": False}]}


@pytest.mark.parametrize("mode", ["unknown_check", "unknown_browser", "duplicate", "claim_success", "no_evidence"])
def test_analysis_cannot_invent_host_authority_or_completion_flags(issue_workspace, mode):
    workspace, _job, _original = issue_workspace
    value = analysis()
    if mode == "unknown_check":
        value["criteria"][0]["checks"] = ["shell"]
    elif mode == "unknown_browser":
        value["criteria"][0]["browser"] = ["external_site"]
    elif mode == "duplicate":
        value["criteria"].append(copy.deepcopy(value["criteria"][0]))
    elif mode == "claim_success":
        value["passed"] = True
    else:
        value["criteria"][0]["checks"] = []
    with pytest.raises(IssueWorkerError):
        RequirementPlan.parse(value, workspace.config)


@pytest.mark.parametrize("mode", ["external", "cloud", "secret_env", "headed", "wrong_port", "extra_field"])
def test_host_browser_contract_refuses_unsafe_or_unknown_execution_fields(mode):
    value = case()
    if mode == "external":
        value["task"]["start_url"] = "https://example.test/"
    elif mode == "cloud":
        value["task"].update({"planner": "ollama", "model": "remote-model"})
    elif mode == "secret_env":
        value["task"]["allowed_env"] = ["GITHUB_TOKEN"]
    elif mode == "headed":
        value["task"]["headless"] = False
    elif mode == "wrong_port":
        value["port"] = 9999
    else:
        value["shell"] = "arbitrary command"
    with pytest.raises(IssueWorkerError):
        scenario_task(value)


def test_requirement_analysis_corrects_one_bad_response_and_binds_source_and_feedback(issue_workspace):
    workspace, job, _original = issue_workspace
    client = CodingPlanner("local-model", error_type=IssueWorkerError)
    responses = [{"message": {"content": "bad json"}}, {"message": {"content": json.dumps(analysis())}}]
    feedback = [{"kind": "review", "body": "Keep the boundary case"}]
    try:
        with patch.object(client, "_request", side_effect=responses) as request:
            result = RequirementAnalyzer(workspace.config, client).analyze(job["snapshot"], feedback, 5)
        assert request.call_count == 2
        assert result["revision"] == requirement_revision(job["snapshot"], feedback)
        assert result["revision"] != requirement_revision(job["snapshot"], [])
        assert request.call_args_list[0].args[2]["format"]["additionalProperties"] is False
    finally:
        client.close()


def run_processor(issue_workspace, plan, browser=None, actions=None):
    workspace, job, _original = issue_workspace
    workspace.config.requirements_enabled = True
    planner = Mock()
    planner.plan.side_effect = actions or [CodeAction("patch", text=PATCH), CodeAction("finish", summary="Fixed")]
    sandbox = Mock()
    sandbox.check.side_effect = lambda root, name, _timeout: {
        "name": name, "passed": True, "tree": root.fingerprint()}
    analyzer = Mock()
    analyzer.analyze.return_value = {**plan, "revision": requirement_revision(job["snapshot"], [])}
    processor = CodeProcessor(workspace.config, planner, sandbox, analyzer, browser)
    outcome = processor.process(job, workspace, Mock(), Redactor())
    return outcome, job, planner, sandbox


def test_ambiguous_requirements_stop_before_baseline_or_patch(issue_workspace):
    plan = analysis()
    plan["questions"], plan["criteria"] = ["Which inputs should return two?"], []
    outcome, job, planner, sandbox = run_processor(issue_workspace, plan)
    assert outcome == "needs_info"
    assert "Which inputs" in job["data"]["reason"]
    assert job["data"]["tool_count"] == 1
    planner.plan.assert_not_called()
    sandbox.check.assert_not_called()


def test_criteria_evidence_is_tree_bound_and_does_not_claim_business_proof(issue_workspace):
    outcome, job, _planner, _sandbox = run_processor(issue_workspace, analysis())
    assert outcome == "ready"
    evidence = job["data"]["acceptance"]["criteria"][0]
    assert evidence["status"] == "evidence_passed" and evidence["business_verified"] is False
    altered = criterion_evidence(job["data"]["analysis"], job["data"], "different-tree")
    assert altered[0]["status"] == "failed"
    provider = Mock(config=issue_workspace[0].config)
    publisher = GitHubPublisher(provider)
    publisher._validate_acceptance(job)
    job["snapshot"]["body"] += "new requirement"
    with pytest.raises(IssueWorkerError, match="acceptance plan"):
        publisher._validate_acceptance(job)


def test_configured_browser_case_is_mandatory_even_if_model_does_not_reference_it(issue_workspace):
    workspace = issue_workspace[0]
    workspace.config.browser_scenarios = {"form": case()}
    browser = Mock()
    browser.signature.return_value = "trusted-case-signature"
    browser.check.side_effect = lambda root, name, _timeout: {
        "name": name, "tree": root.fingerprint(), "signature": "trusted-case-signature", "passed": False}
    actions = [CodeAction("patch", text=PATCH), CodeAction("finish", summary="first"),
               CodeAction("finish", summary="second")]
    outcome, job, _planner, _sandbox = run_processor(issue_workspace, analysis(), browser, actions)
    assert outcome == "failed"
    assert "validated_tree" not in job["data"]
    assert browser.check.call_count == 2


def test_browser_boundary_uses_trusted_code_and_rejects_forged_tree_evidence(issue_workspace):
    workspace = issue_workspace[0]
    workspace.config.browser_scenarios = {"form": case()}
    validator = BrowserAcceptance(workspace.config)
    captured = []

    def execute(_sandbox, argv, _container, _output, _timeout):
        captured.extend(argv)
        mounts = [argv[index + 1] for index, item in enumerate(argv) if item == "--mount"]
        manifest_mount = next(item for item in mounts if "destination=/manifest/plan.json" in item)
        manifest_path = Path(manifest_mount.split("src=", 1)[1].split(",destination=", 1)[0])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "GITHUB_TOKEN" not in manifest
        report = {"status": "success", "tree": "forged-tree", "signature": manifest["signature"]}
        return {"passed": True, "exit_code": 0, "output": "WEBRUNNER_BROWSER_RESULT=" + json.dumps(report)}

    with patch("je_web_runner.utils.issue_worker.browser_acceptance.PodmanSandbox._execute", execute):
        result = validator.check(workspace, "form", 10)
    assert result["passed"] is False
    assert "--network=none" in captured and "--read-only" in captured
    assert "PYTHONPATH=/trusted" in captured
    assert "/trusted/entry.py" in captured
    assert validator.signature("form") == result["signature"]


def test_browser_scenarios_are_closed_host_config(tmp_path):
    config = IssueWorkerConfig(str(tmp_path / "state"), "model", "bot", browser_scenarios={"form": case()})
    assert config.browser_scenarios["form"]["port"] == 8765
    with pytest.raises(IssueWorkerError):
        IssueWorkerConfig(str(tmp_path), "model", "bot", browser_scenarios={"../escape": case()})


def test_browser_entry_fails_closed_before_starting_app_when_process_protection_fails(tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"case": case(), "tree": "tree", "signature": "signature"}), encoding="utf-8")
    with patch("je_web_runner.utils.issue_worker.browser_entry.sys.platform", "linux"), \
            patch("je_web_runner.utils.issue_worker.browser_entry.ctypes.CDLL") as library, \
            patch("je_web_runner.utils.issue_worker.browser_entry.execute_case") as execute:
        library.return_value.prctl.return_value = -1
        assert browser_main(str(manifest)) == 1
        execute.assert_not_called()
    assert "RuntimeError" in capsys.readouterr().out


def test_worktree_cannot_replace_the_trusted_browser_verifier(issue_workspace):
    workspace = issue_workspace[0]
    workspace.config.browser_scenarios = {"form": case()}
    workspace.patch("diff --git a/je_web_runner/utils/issue_worker/browser_entry.py "
                    "b/je_web_runner/utils/issue_worker/browser_entry.py\nnew file mode 100644\n"
                    "--- /dev/null\n+++ b/je_web_runner/utils/issue_worker/browser_entry.py\n"
                    "@@ -0,0 +1 @@\n+APP_FAKE_SUCCESS = True\n")
    validator = BrowserAcceptance(workspace.config)

    def execute(_sandbox, argv, _container, _output, _timeout):
        mounts = [argv[index + 1] for index, value in enumerate(argv) if value == "--mount"]

        def source(destination):
            mount = next(item for item in mounts if "destination=" + destination + "," in item)
            return Path(mount.split("src=", 1)[1].split(",destination=", 1)[0])

        assert "APP_FAKE_SUCCESS" not in (source("/trusted") / "entry.py").read_text(encoding="utf-8")
        assert "APP_FAKE_SUCCESS" in (source("/work") / "je_web_runner/utils/issue_worker/browser_entry.py").read_text()
        manifest = json.loads(source("/manifest/plan.json").read_text(encoding="utf-8"))
        report = {"status": "success", "tree": manifest["tree"], "signature": manifest["signature"],
                  "conditions_verified": 1}
        return {"passed": True, "exit_code": 0, "output": "WEBRUNNER_BROWSER_RESULT=" + json.dumps(report)}

    with patch("je_web_runner.utils.issue_worker.browser_acceptance.PodmanSandbox._execute", execute):
        result = validator.check(workspace, "form", 10)
    assert result["passed"] is True


def test_optional_real_podman_browser_acceptance(issue_workspace):
    image = os.environ.get("WEBRUNNER_ISSUE_IMAGE")
    if not image or not shutil.which("podman"):
        if os.environ.get("WEBRUNNER_ISSUE_REAL_TESTS") == "1":
            pytest.fail("required browser acceptance needs Podman and WEBRUNNER_ISSUE_IMAGE")
        pytest.skip("set WEBRUNNER_ISSUE_IMAGE and install Podman for the real browser verifier")
    workspace = issue_workspace[0]
    workspace.config.image = image
    workspace.patch("diff --git a/examples/index.html b/examples/index.html\nnew file mode 100644\n"
                    "--- /dev/null\n+++ b/examples/index.html\n@@ -0,0 +1,3 @@\n"
                    "+<p id='result'>waiting</p>\n"
                    "+<button id='submit' onclick=\"document.querySelector('#result').textContent='Hello'\">\n"
                    "+Submit</button>\n")
    workspace.patch("diff --git a/examples/server.py b/examples/server.py\nnew file mode 100644\n"
                    "--- /dev/null\n+++ b/examples/server.py\n@@ -0,0 +1,12 @@\n"
                    "+import http.server, os\n+try:\n"
                    "+    handle = os.open(f'/proc/{os.getppid()}/fd/1', os.O_WRONLY)\n"
                    "+except OSError:\n+    denied = True\n+else:\n+    os.close(handle)\n+    denied = False\n"
                    "+if not denied:\n+    raise RuntimeError('verifier descriptors exposed')\n"
                    "+os.chdir('/work/examples')\n"
                    "+http.server.test(HandlerClass=http.server.SimpleHTTPRequestHandler, "
                    "port=8765, bind='127.0.0.1')\n")
    profile = case()
    profile["server"] = ["python", "/work/examples/server.py"]
    profile["task"].update({"backend": "playwright", "timeout": 60})
    workspace.config.browser_scenarios = {"form": profile}
    result = BrowserAcceptance(workspace.config).check(workspace, "form", 90)
    assert result["passed"] is True, result
    assert result["evidence"]["conditions_verified"] == 1
