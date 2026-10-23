"""Shared isolated git fixtures for issue coding and lifecycle tests."""
import pytest
from je_web_runner.utils.issue_worker.types import IssueSnapshot, IssueWorkerConfig
from je_web_runner.utils.issue_worker.workspace import IssueWorkspace, git_run


@pytest.fixture
def issue_workspace(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "je_web_runner").mkdir()
    (original / "test").mkdir()
    (original / "je_web_runner/calc.py").write_text("def value():\n    return 1\n", newline="\n")
    (original / "test/test_calc.py").write_text("def test_value():\n    assert 1 == 1\n", newline="\n")
    git_run(original, ["init", "-b", "dev"])
    git_run(original, ["add", "--", "je_web_runner/calc.py", "test/test_calc.py"])
    git_run(original, ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-m", "Baseline"])
    config = IssueWorkerConfig(str(tmp_path / "state"), "local-model", "worker-bot", checks={"unit": ["python", "-V"]})
    snapshot = IssueSnapshot("github", "12", "Change value", "Acceptance: value is two", "https://example.test/12",
                             ("automation-ready",))
    job = {"key": snapshot.key, "snapshot": snapshot.to_dict(), "run": 1, "data": {}}
    isolated = IssueWorkspace.prepare(config, job, remote=str(original))
    return isolated, job, original
