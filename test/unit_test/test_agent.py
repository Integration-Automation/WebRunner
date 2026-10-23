"""Agent contracts, bounded execution, deterministic verification and secret handling."""
from unittest.mock import Mock, patch
import logging

import pytest

from je_web_runner.api.ai import AgentAction, AgentError, AgentRunner, SuccessCondition, TaskSpec
from je_web_runner.utils.agent.planners import OllamaPlanner
from je_web_runner.utils.agent.runner import Redactor, agent_session


class FakeBrowser:
    """In-memory page that changes only when the configured operation succeeds."""

    def __init__(self):
        self.url = "http://localhost/start"
        self.content = "waiting"
        self.actions = []
        self.closed = False
        self.error = None

    def set_timeout(self, timeout):
        self.timeout = timeout

    def perform(self, action):
        self.actions.append(action)
        if self.error:
            raise self.error
        if action.kind == "navigate":
            self.url = action.value
        if action.kind == "click":
            self.content = "completed"
        if action.kind == "extract":
            return self.content
        return None

    def observe(self, step):
        return {"url": self.url, "title": "demo", "text": self.content, "elements": [], "step": step}

    def text(self, selector="body", frame=""):
        return self.content

    def visible(self, selector, frame=""):
        return self.content == "completed"

    def close(self):
        self.closed = True

    def screenshot(self, path, secrets):
        path.write_bytes(b"masked screenshot")


def task(**changes):
    values = dict(goal="Complete the demo", start_url="http://localhost/start",
                  success=[SuccessCondition("text_contains", value="completed")],
                  steps=[AgentAction("click", "#go")], action_timeout=0.01)
    values.update(changes)
    return TaskSpec(**values)


@pytest.mark.parametrize("changes", [
    {"timeout": True}, {"timeout": float("nan")}, {"max_steps": 1.5}, {"success": []},
    {"start_url": "file:///secret"}, {"start_url": "https://user:secret@example.test"},
    {"planner": "cloud"}, {"planner": "ollama"}, {"allowed_env": ["INVALID-NAME"]},
])
def test_task_validation_precedes_browser_launch(changes):
    with pytest.raises(AgentError):
        task(**changes)


def test_json_task_is_closed_and_typed():
    parsed = TaskSpec.from_dict({"goal": "Read a result", "start_url": "http://localhost/demo",
                                "success": [{"kind": "visible", "selector": "#result"}],
                                "steps": [{"kind": "wait", "selector": "#result"}]})
    assert parsed.steps[0].kind == "wait"
    with pytest.raises(AgentError):
        TaskSpec.from_dict({"goal": "x", "start_url": "http://localhost", "unknown": True})
    with pytest.raises(AgentError):
        AgentAction.from_dict({"kind": "click", "selector": "#x", "script": "secret"})
    with pytest.raises(AgentError):
        AgentAction.from_dict({"kind": "execute_script", "value": "alert(1)"})


def test_last_allowed_step_can_succeed_and_borrowed_browser_stays_open():
    browser = FakeBrowser()
    report = AgentRunner(task(max_steps=1), browser=browser).run()
    assert report.status == "success"
    assert len(report.steps) == 1
    assert not browser.closed


def test_owned_browser_is_closed_after_verified_success():
    browser = FakeBrowser()
    with patch("je_web_runner.utils.agent.runner.BrowserSession.open", return_value=browser):
        report = AgentRunner(task()).run()
    assert report.status == "success"
    assert browser.closed


def test_done_without_verified_result_fails():
    report = AgentRunner(task(steps=[]), browser=FakeBrowser()).run()
    assert report.status == "failed"
    assert "before success conditions" in report.stopped_reason


def test_identical_state_and_action_stops_after_three_proposals():
    browser = FakeBrowser()
    planner = Mock()
    planner.plan.return_value = AgentAction("scroll")
    report = AgentRunner(task(), browser=browser, planner=planner).run()
    assert report.status == "failed"
    assert "three consecutive" in report.stopped_reason
    assert len(report.steps) == 2


def test_planner_may_not_execute_after_task_deadline():
    browser = FakeBrowser()
    planner = Mock()
    runner = AgentRunner(task(), browser=browser, planner=planner)

    def expire(_observation, _timeout):
        runner.deadline = 0
        return AgentAction("click", "#go")

    planner.plan.side_effect = expire
    report = runner.run()
    assert report.status == "timeout"
    assert [action.kind for action in browser.actions] == ["navigate"]


def test_failed_action_is_not_replayed_and_screenshot_is_recorded(tmp_path):
    browser = FakeBrowser()
    original = browser.perform

    def fail_click(action):
        if action.kind == "click":
            browser.error = RuntimeError("submission failed after dispatch")
        return original(action)

    browser.perform = fail_click
    report = AgentRunner(task(), browser=browser, artifact_dir=tmp_path).run()
    assert report.status == "failed"
    assert [action.kind for action in browser.actions].count("click") == 1
    assert report.steps[0]["status"] == "failed"
    assert report.artifacts == [str((tmp_path / "failure.png").resolve())]


def test_extraction_and_all_conditions_are_verified():
    browser = FakeBrowser()
    report = AgentRunner(task(
        extract={"answer": "#answer"},
        success=[SuccessCondition("visible", selector="#answer"),
                 SuccessCondition("url_contains", value="localhost"),
                 SuccessCondition("extracted_equals", key="answer", value="completed")],
    ), browser=browser).run()
    assert report.status == "success"
    assert report.extracted == {"answer": "completed"}


def test_environment_values_never_reach_report_or_model_observation(monkeypatch):
    monkeypatch.setenv("DEMO_AGENT_PASSWORD", "private-value-123")
    browser = FakeBrowser()
    planner = Mock()
    planner.plan.side_effect = [AgentAction("fill", "#password", "${ENV.DEMO_AGENT_PASSWORD}"),
                                AgentAction("click", "#go")]
    report = AgentRunner(task(allowed_env=["DEMO_AGENT_PASSWORD"]), browser=browser, planner=planner).run()
    assert report.status == "success"
    assert browser.actions[1].value == "private-value-123"
    assert "private-value-123" not in str(report.to_dict())
    assert report.steps[0]["action"]["value"] == "<hidden>"
    assert "private-value-123" not in str(planner.plan.call_args_list)


def test_unlisted_environment_value_is_not_read(monkeypatch):
    monkeypatch.setenv("DEMO_AGENT_PASSWORD", "private-value-123")
    redactor = Redactor()
    with pytest.raises(AgentError, match="not allowed"):
        redactor.resolve(AgentAction("fill", "#x", "${ENV.DEMO_AGENT_PASSWORD}"), [])


def test_concurrent_agent_requests_are_rejected():
    with agent_session():
        with pytest.raises(AgentError, match="another agent"):
            AgentRunner(task(), browser=FakeBrowser()).run()


def test_transport_debug_logs_do_not_capture_input_values(caplog):
    browser = FakeBrowser()
    original = browser.perform

    def logging_action(action):
        logging.getLogger("selenium.webdriver.remote.remote_connection").debug("raw value: private-password")
        return original(action)

    browser.perform = logging_action
    with caplog.at_level(logging.DEBUG):
        assert AgentRunner(task(), browser=browser).run().status == "success"
    assert "private-password" not in caplog.text
    logger = logging.getLogger("selenium.webdriver.remote.remote_connection")
    assert not logger.filters


def test_runner_cannot_reuse_a_closed_session_or_exhausted_planner():
    runner = AgentRunner(task(), browser=FakeBrowser())
    assert runner.run().status == "success"
    with pytest.raises(AgentError, match="already ran"):
        runner.run()


@pytest.mark.parametrize("endpoint", ["https://api.example.test", "http://127.0.0.1.example.test", "http://localhost/u"])
def test_ollama_endpoint_is_local_only(endpoint):
    with pytest.raises(AgentError):
        OllamaPlanner(task(planner="ollama", model="local-model"), endpoint)


def local_planner():
    return OllamaPlanner(task(planner="ollama", model="local-model"))


def test_ollama_preflight_requires_cloud_disabled_and_local_weights():
    planner = local_planner()
    try:
        with patch.object(planner, "_request", return_value={"cloud": {"disabled": False}}):
            with pytest.raises(AgentError, match="OLLAMA_NO_CLOUD"):
                planner.preflight(1)
        with patch.object(planner, "_request", side_effect=[
            {"cloud": {"disabled": True}}, {"models": [{"name": "local-model:latest", "remote_model": "remote"}]},
        ]):
            with pytest.raises(AgentError, match="not installed"):
                planner.preflight(1)
    finally:
        planner.close()


def test_local_planner_repairs_invalid_json_once_then_stops():
    planner = local_planner()
    try:
        with patch.object(planner, "_request", side_effect=[
            {"message": {"content": "invalid"}}, {"message": {"content": '{"kind":"click","selector":"#go"}'}},
        ]) as request:
            assert planner.plan({}, 1) == AgentAction("click", "#go")
            assert request.call_count == 2
        with patch.object(planner, "_request", return_value={"message": {"content": "invalid"}}) as request:
            with pytest.raises(AgentError, match="twice"):
                planner.plan({}, 1)
            assert request.call_count == 2
        assert planner.session.trust_env is False
    finally:
        planner.close()


def test_failed_preflight_does_not_launch_a_browser():
    planner = Mock()
    planner.preflight.side_effect = AgentError("local model unavailable")
    with patch("je_web_runner.utils.agent.runner.BrowserSession.open") as launch:
        report = AgentRunner(task(), planner=planner).run()
    assert report.status == "failed"
    launch.assert_not_called()
