"""Real isolated git patches, coding bounds and immutable sandbox policy."""
import os
import shutil
from unittest.mock import Mock

import pytest

from je_web_runner.utils.agent.runner import Redactor
from je_web_runner.utils.issue_worker.planner import CodeAction
from je_web_runner.utils.issue_worker.policy import checked_path, preserve_tests
from je_web_runner.utils.issue_worker.processor import CodeProcessor
from je_web_runner.utils.issue_worker.sandbox import PodmanSandbox, transport_environment
from je_web_runner.utils.issue_worker.types import IssueWorkerError
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace

PATCH = """diff --git a/je_web_runner/calc.py b/je_web_runner/calc.py
--- a/je_web_runner/calc.py
+++ b/je_web_runner/calc.py
@@ -1,2 +1,2 @@
 def value():
-    return 1
+    return 2
"""




def test_real_patch_updates_only_private_worktree_and_reopens_checkpoint(issue_workspace):
    isolated, job, original = issue_workspace
    assert isolated.patch(PATCH) == ["je_web_runner/calc.py"]
    assert "return 2" in isolated.read("je_web_runner/calc.py")
    assert "return 1" in (original / "je_web_runner/calc.py").read_text()
    job["data"]["base_sha"] = isolated.base_sha
    resumed = IssueWorkspace.prepare(isolated.config, job, remote=str(original))
    assert resumed.fingerprint() == isolated.fingerprint()
    assert resumed.changes()[0][2] == "je_web_runner/calc.py"


@pytest.mark.parametrize("path", ["../outside", "/etc/passwd", "C:/Windows/file", ".git/config", ".env"])
def test_coding_paths_do_not_escape_worktree(tmp_path, path):
    with pytest.raises(IssueWorkerError):
        checked_path(tmp_path, path)


@pytest.mark.parametrize("path", [".github/workflows/test.yml", "pyproject.toml", "scripts/dev_release.py",
                                  "docs/requirements.txt", "je_web_runner/AGENTS.md"])
def test_model_cannot_patch_host_policy_or_dependencies(tmp_path, path):
    with pytest.raises(IssueWorkerError):
        checked_path(tmp_path, path, write=True)


def test_over_budget_patch_rolls_back_index_and_files(issue_workspace):
    isolated, _job, _original = issue_workspace
    tree = isolated.fingerprint()
    isolated.config.max_lines = 1
    with pytest.raises(IssueWorkerError, match="limits"):
        isolated.patch(PATCH)
    assert isolated.fingerprint() == tree
    assert "return 1" in isolated.read("je_web_runner/calc.py")


def test_test_assertion_guard_rejects_weakening_or_skip():
    before = "def test_result():\n    assert result() == 2\n"
    with pytest.raises(IssueWorkerError, match="assertion"):
        preserve_tests(before, "def test_result():\n    assert True\n")
    with pytest.raises(IssueWorkerError, match="skip"):
        preserve_tests(before, "import pytest\n@pytest.mark.skip\n" + before)
    preserve_tests(before, before + "\ndef test_new():\n    assert result() > 0\n")


def test_source_export_has_no_git_database_or_credentials(issue_workspace, tmp_path):
    isolated, _job, _original = issue_workspace
    destination = tmp_path / "export"
    isolated.export(destination)
    assert (destination / "je_web_runner/calc.py").is_file()
    assert not (destination / ".git").exists()


def test_sandbox_policy_and_host_environment_are_not_model_controlled(issue_workspace, tmp_path, monkeypatch):
    isolated, _job, _original = issue_workspace
    monkeypatch.setenv("GITHUB_TOKEN", "fixture-sensitive-token")
    sandbox = PodmanSandbox(isolated.config)
    command = sandbox.argv(isolated, "unit", tmp_path, "fixture-container")
    assert "--network=none" in command
    assert "--pull=never" in command
    assert "--read-only" in command
    assert "--cap-drop=ALL" in command
    assert "ro=true" in command[command.index("--mount") + 1]
    assert "GITHUB_TOKEN" not in transport_environment()
    assert "fixture-sensitive-token" not in str(command)
    with pytest.raises(IssueWorkerError, match="unknown"):
        sandbox.argv(isolated, "arbitrary-shell", tmp_path, "fixture-container")


def processor(issue_workspace, actions, passed=True):
    isolated, job, _original = issue_workspace
    planner = Mock()
    planner.plan.side_effect = actions
    sandbox = Mock()
    sandbox.check.side_effect = lambda root, name, timeout: {
        "name": name, "passed": passed, "tree": root.fingerprint(), "output": "fixture validation",
    }
    checkpoints = []
    engine = CodeProcessor(isolated.config, planner, sandbox)
    outcome = engine.process(job, isolated, lambda state, data: checkpoints.append(state), Redactor())
    return outcome, job, checkpoints, sandbox


def test_local_coding_finish_requires_actual_host_checks_and_matching_tree(issue_workspace):
    outcome, job, checkpoints, sandbox = processor(issue_workspace, [CodeAction("patch", text=PATCH),
                                                              CodeAction("finish", summary="Updated return value")])
    assert outcome == "ready"
    assert job["data"]["validated_tree"] == issue_workspace[0].fingerprint()
    assert sandbox.check.call_count == 2  # original baseline and patched final tree
    assert "validating" in checkpoints


def test_model_finish_without_changes_cannot_publish(issue_workspace):
    outcome, job, _checkpoints, _sandbox = processor(issue_workspace, [CodeAction("finish", summary="Done")] * 2)
    assert outcome == "failed"
    assert "no code" in job["data"]["reason"]


def test_failed_validation_exhausts_repair_rounds(issue_workspace):
    actions = [CodeAction("patch", text=PATCH), CodeAction("finish", summary="first"),
               CodeAction("finish", summary="second")]
    outcome, job, _checkpoints, _sandbox = processor(issue_workspace, actions, passed=False)
    assert outcome == "failed"
    assert job["data"]["validation_rounds"] == 2
    assert "validated_tree" not in job["data"]


def test_ambiguous_issue_returns_concrete_questions_without_changes(issue_workspace):
    outcome, job, _checkpoints, _sandbox = processor(issue_workspace, [
        CodeAction("needs_info", summary="Which input should produce this result?"),
    ])
    assert outcome == "needs_info"
    assert "Which input" in job["data"]["reason"]
    assert issue_workspace[0].changes() == []


def test_optional_real_podman_isolation(issue_workspace):
    image = os.environ.get("WEBRUNNER_ISSUE_IMAGE")
    if not image or not shutil.which("podman"):
        pytest.skip("set WEBRUNNER_ISSUE_IMAGE and install Podman to verify a real offline container")
    isolated, _job, _original = issue_workspace
    isolated.config.image = image
    isolated.config.checks = {"unit": ["python", "-c",
        "import os,pathlib; assert not os.getenv('GITHUB_TOKEN'); assert not pathlib.Path('/work/.git').exists(); "
        "assert pathlib.Path('/work/je_web_runner/calc.py').is_file(); print('isolation verified')"]}
    sandbox = PodmanSandbox(isolated.config)
    sandbox.preflight()
    result = sandbox.check(isolated, "unit", 30)
    assert result["passed"], result
    assert "isolation verified" in result["output"]
