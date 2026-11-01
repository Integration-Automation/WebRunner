"""Real isolated git patches, coding bounds and immutable sandbox policy."""
import os
import json
import shutil
import time
from unittest.mock import Mock, patch

import pytest

from je_web_runner.utils.agent.runner import Redactor
from je_web_runner.utils.issue_worker.planner import CODE_SCHEMA, CodeAction, CodingPlanner
from je_web_runner.utils.issue_worker.policy import checked_path, preserve_tests
from je_web_runner.utils.issue_worker.processor import CodeProcessor
from je_web_runner.utils.issue_worker.sandbox import PodmanSandbox, transport_environment
from je_web_runner.utils.issue_worker.types import EnvironmentUnavailable, IssueWorkerError
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace, git_run

PATCH = """diff --git a/je_web_runner/calc.py b/je_web_runner/calc.py
--- a/je_web_runner/calc.py
+++ b/je_web_runner/calc.py
@@ -1,2 +1,2 @@
 def value():
-    return 1
+    return 2
"""




@pytest.mark.parametrize("final_newline", [True, False])
@pytest.mark.parametrize("hunk_count", ["2", "99"])
def test_real_patch_updates_only_private_worktree_and_reopens_checkpoint(issue_workspace, final_newline, hunk_count):
    isolated, job, original = issue_workspace
    proposal = PATCH.replace("@@ -1,2 +1,2 @@", f"@@ -1,{hunk_count} +1,{hunk_count} @@")
    assert isolated.patch(proposal if final_newline else proposal.rstrip("\n")) == ["je_web_runner/calc.py"]
    assert "return 2" in isolated.read("je_web_runner/calc.py")
    assert "return 1" in (original / "je_web_runner/calc.py").read_text()
    job["data"]["base_sha"] = isolated.base_sha
    resumed = IssueWorkspace.prepare(isolated.config, job, remote=str(original))
    assert resumed.fingerprint() == isolated.fingerprint()
    assert resumed.changes()[0][2] == "je_web_runner/calc.py"


@pytest.mark.parametrize("invalid,expected", [
    ("@@ -1,3 +1,3 @@\n-def value():\n+def value():\n     return 2", "complete git unified diff"),
    (PATCH.replace("-    return 1", "-    return 99"), "read them"),
])
def test_rejected_patch_gives_repair_guidance_without_changing_the_index(issue_workspace, invalid, expected):
    isolated = issue_workspace[0]
    before = isolated.fingerprint()
    with pytest.raises(IssueWorkerError, match=expected):
        isolated.patch(invalid)
    assert isolated.fingerprint() == before
    assert isolated.changes() == []
    isolated.patch(PATCH)
    assert "return 2" in isolated.read("je_web_runner/calc.py")


def test_staged_diff_preview_is_bounded_and_explicitly_marks_omitted_content(issue_workspace):
    isolated = issue_workspace[0]
    baseline_tree = isolated.fingerprint()
    initial = isolated.preview()
    assert initial["tree"] == baseline_tree and initial["diff"] == "" and not initial["truncated"]
    isolated.patch(PATCH.replace("+    return 2", '+    return "' + "A" * 18000 + '"'))
    draft = isolated.preview()
    assert len(draft["diff"]) == 16000 and draft["truncated"] is True
    assert draft["tree"] == isolated.fingerprint() and draft["tree"] != baseline_tree
    assert draft["base_commit"] == isolated.base_sha


def test_staged_diff_preview_refuses_credentials_even_if_staged_outside_the_patch_tool(issue_workspace):
    isolated = issue_workspace[0]
    (isolated.root / ".env").write_text("SYNTHETIC_SECRET=fixture-private-value", encoding="utf-8")
    git_run(isolated.root, ["add", "--", ".env"])
    with pytest.raises(IssueWorkerError, match="credential") as error:
        isolated.preview()
    assert "fixture-private-value" not in str(error.value)


@pytest.mark.parametrize("path", ["../outside", "/etc/passwd", "C:/Windows/file", ".git/config", ".env"])
def test_coding_paths_do_not_escape_worktree(tmp_path, path):
    with pytest.raises(IssueWorkerError):
        checked_path(tmp_path, path)


@pytest.mark.parametrize("path", [".github/workflows/test.yml", "pyproject.toml", "scripts/dev_release.py",
                                  "docs/requirements.txt", "je_web_runner/AGENTS.md"])
def test_model_cannot_patch_host_policy_or_dependencies(tmp_path, path):
    with pytest.raises(IssueWorkerError):
        checked_path(tmp_path, path, write=True)


@pytest.mark.parametrize("hunk_count", ["2", "99"])
def test_over_budget_patch_rolls_back_index_and_files(issue_workspace, hunk_count):
    isolated, _job, _original = issue_workspace
    tree = isolated.fingerprint()
    isolated.config.max_lines = 1
    with pytest.raises(IssueWorkerError, match="limits"):
        isolated.patch(PATCH.replace("@@ -1,2 +1,2 @@", f"@@ -1,{hunk_count} +1,{hunk_count} @@"))
    assert isolated.fingerprint() == tree
    assert "return 1" in isolated.read("je_web_runner/calc.py")


@pytest.mark.parametrize("history,can_edit", [([], False),
    ([{"action": {"kind": "read"}, "error": "absent"}], False),
    ([{"action": {"kind": "read"}, "result": "def value(): return 1"}], True),
    ([{"action": {"kind": "search"}, "result": []}], True)])
def test_local_planner_allows_editing_only_after_successful_repository_inspection(history, can_edit):
    client = CodingPlanner("local-model", error_type=IssueWorkerError)
    try:
        with patch.object(client, "structured", return_value=CodeAction("read", path="je_web_runner/calc.py")) as plan:
            client.plan({"history": history}, 5)
        kinds = {variant["properties"]["kind"]["const"] for variant in plan.call_args.args[2]["oneOf"]}
        assert ("patch" in kinds) is can_edit
        assert {"read", "search", "needs_info"}.issubset(kinds)
        assert "patch" in {variant["properties"]["kind"]["const"] for variant in CODE_SCHEMA["oneOf"]}
    finally:
        client.close()


@pytest.mark.parametrize("kind,field", [("read", "path"), ("search", "text"), ("patch", "text"),
                                      ("check", "check"), ("finish", "summary"), ("needs_info", "summary")])
def test_model_response_cannot_combine_arguments_for_different_operations(kind, field):
    value = {"kind": kind, field: "value"}
    assert CodeAction.from_dict(value).kind == kind
    extra = "path" if field != "path" else "summary"
    with pytest.raises(IssueWorkerError, match="only the fields"):
        CodeAction.from_dict({**value, extra: "a different operation"})


def test_grounded_schema_and_parser_both_require_initial_repository_inspection():
    client = CodingPlanner("local-model", error_type=IssueWorkerError)
    responses = [{"message": {"content": json.dumps({"kind": "patch", "text": PATCH})}},
                 {"message": {"content": json.dumps({"kind": "read", "path": "je_web_runner/calc.py"})}}]
    try:
        with patch.object(client, "_request", side_effect=responses) as request:
            result = client.plan({"history": []}, 5)
        assert result.kind == "read" and request.call_count == 2
        payload = request.call_args_list[0].args[2]
        embedded = payload["messages"][0]["content"].split("\nJSON schema:\n", 1)[1]
        assert json.loads(embedded) == payload["format"]
        assert {item["properties"]["kind"]["const"] for item in payload["format"]["oneOf"]} == {
            "read", "search", "needs_info"}
    finally:
        client.close()


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


def test_planner_sees_applied_diff_and_historical_baseline_before_requesting_final_checks(issue_workspace):
    workspace, job, _original = issue_workspace
    baseline_tree = workspace.fingerprint()
    planner, sandbox = Mock(), Mock()

    def request_validation(context, _timeout):
        assert "-    return 1" in context["current_diff"]
        assert "+    return 2" in context["current_diff"]
        assert context["current_tree"] == workspace.fingerprint()
        assert context["baseline"]["historical"] is True
        assert context["baseline"]["applies_to_current_tree"] is False
        assert context["baseline"]["passed"] is False
        assert context["checks"] == {}  # A draft diff does not fabricate current test success.
        return CodeAction("finish", summary="Ready for the host's independent final checks")

    planner.plan.side_effect = lambda context, timeout: (
        CodeAction("patch", text=PATCH) if not context["history"] else request_validation(context, timeout))
    sandbox.check.side_effect = lambda root, name, _timeout: {
        "name": name, "passed": root.fingerprint() != baseline_tree, "tree": root.fingerprint()}
    engine = CodeProcessor(workspace.config, planner, sandbox)
    assert engine.process(job, workspace, Mock(), Redactor()) == "ready"
    assert sandbox.check.call_count == 2
    assert job["data"]["baseline"]["passed"] is False
    assert "historical" not in job["data"]["baseline"]
    assert job["data"]["validated_tree"] == workspace.fingerprint()


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


def test_coding_loop_can_read_and_retry_after_a_rejected_model_patch(issue_workspace):
    actions = [CodeAction("patch", text="@@ -1 +1 @@\n-old\n+new"),
               CodeAction("read", path="je_web_runner/calc.py"), CodeAction("patch", text=PATCH),
               CodeAction("finish", summary="Fixed the return value after inspecting its implementation")]
    outcome, job, _checkpoints, _sandbox = processor(issue_workspace, actions)
    assert outcome == "ready"
    first, read, applied = job["data"]["history"]
    assert first["action"]["text"] == "<patch rejected>"
    assert "file headers" in first["error"]
    assert "return 1" in read["result"]
    assert applied["action"]["text"] == "<patch applied to files and git index>"


@pytest.mark.parametrize("analysis_phase", [False, True])
def test_inference_timeout_at_the_job_deadline_is_attributed_to_the_time_budget(issue_workspace, analysis_phase):
    workspace, job, _original = issue_workspace
    planner, analyzer = Mock(), Mock()
    engine = CodeProcessor(workspace.config, planner, Mock(), analyzer)
    data = job["data"]
    data["deadline"] = time.time() + 60
    data["tool_count"] = 0

    def timed_out(*_args):
        data["deadline"] = time.time() - 1
        raise IssueWorkerError("local request timed out")

    planner.plan.side_effect = analyzer.analyze.side_effect = timed_out
    with pytest.raises(IssueWorkerError, match="total time limit"):
        if analysis_phase:
            engine._analyze(job, data, Mock(), Redactor())
        else:
            engine._plan({}, data)
    assert data["reason_code"] == "time_budget"
    planner.preflight.assert_not_called()


def test_requirement_inference_dependency_outage_is_deferred_before_any_baseline_or_patch(issue_workspace):
    workspace, job, _original = issue_workspace
    workspace.config.requirements_enabled = True
    planner, analyzer, sandbox = Mock(), Mock(), Mock()
    analyzer.analyze.side_effect = IssueWorkerError("local request failed")
    planner.preflight.side_effect = IssueWorkerError("local service unavailable")
    engine = CodeProcessor(workspace.config, planner, sandbox, analyzer)
    with pytest.raises(EnvironmentUnavailable):
        engine.process(job, workspace, Mock(), Redactor())
    sandbox.check.assert_not_called()
    planner.plan.assert_not_called()


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
        if os.environ.get("WEBRUNNER_ISSUE_REAL_TESTS") == "1":
            pytest.fail("real acceptance requires Podman and WEBRUNNER_ISSUE_IMAGE")
        pytest.skip("set WEBRUNNER_ISSUE_IMAGE and install Podman to verify a real offline container")
    isolated, _job, _original = issue_workspace
    isolated.config.image = image
    probe = """import os, pathlib, socket
assert os.getuid() != 0
assert not any(os.getenv(key) for key in ('GITHUB_TOKEN', 'JIRA_API_TOKEN', 'FIXTURE_GH_TOKEN'))
assert not pathlib.Path('/work/.git').exists()
assert pathlib.Path('/work/je_web_runner/calc.py').is_file()
for target in ('/work/forbidden', '/etc/forbidden'):
    try:
        pathlib.Path(target).write_text('forbidden')
    except OSError:
        continue
    raise AssertionError('read-only mount allowed a write')
try:
    connection = socket.create_connection(('192.0.2.1', 9), timeout=0.2)
except OSError:
    print('isolation verified')
else:
    connection.close()
    raise AssertionError('offline container reached an external address')
"""
    isolated.config.checks = {"unit": ["python", "-c", probe]}
    sandbox = PodmanSandbox(isolated.config)
    sandbox.preflight()
    result = sandbox.check(isolated, "unit", 30)
    assert result["passed"], result
    assert "isolation verified" in result["output"]
    isolated.config.checks = {"timeout": ["python", "-c", "import time; time.sleep(30)"]}
    result = sandbox.check(isolated, "timeout", 0.5)
    assert not result["passed"] and "limit" in result["reason"]
    # Force cleanup already ran; recovery must find no residual containers in this unique state scope.
    with patch.object(sandbox, "_remove_container", wraps=sandbox._remove_container) as remove:
        sandbox.recover()
    remove.assert_not_called()
