"""Free local agent round trips against an HTTP fixture, with real headless browsers."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from je_web_runner.api.ai import AgentAction, AgentRunner, SuccessCondition, TaskSpec
from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.agent.planners import OllamaPlanner
from je_web_runner.utils.agent.types import AgentError
from je_web_runner.utils.smart_wait import wait_for_fetch_idle, wait_for_spa_route_stable

_FORM = """<!doctype html><title>Local agent demo</title>
<label>Name <input id="name"></label><input id="password" type="password">
<button id="submit" onclick="document.querySelector('#result').textContent=
'Hello '+document.querySelector('#name').value">
Submit</button><p id="result">waiting</p><a href="/search" id="search">Search</a>
<iframe id="frame" src="/frame"></iframe><div style="height:1600px"></div>"""
_SEARCH = """<!doctype html><title>Search demo</title><input id="query">
<button id="find" onclick="location.href='/details?q='+encodeURIComponent(document.querySelector('#query').value)">
Find</button>"""
_FRAME = """<label>Message <input id="message"></label>
<button id="send" onclick="document.querySelector('#reply').textContent='sent'">Send</button>
<p id="reply">waiting</p>"""


@pytest.fixture(scope="module")
def local_site():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            pages = {"/": _FORM, "/search": _SEARCH, "/frame": _FRAME,
                     "/details": '<title>Details</title><p id="answer">42</p>'}
            route = self.path.split("?")[0]
            if route in {"/index.html", "/search.html", "/frame.html", "/details.html"}:
                content = Path(__file__).resolve().parents[2] / "examples" / "agent_demo" / route[1:]
                body = content.read_bytes()
            else:
                body = pages.get(route, "not found").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="module", params=["selenium", "playwright"])
def browser(request):
    try:
        if request.param == "playwright":
            from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper
            owner = PlaywrightWrapper()
            # The installed Chrome channel avoids downloading a separate browser for this fixture.
            owner.launch(channel="chrome", headless=True)
            session = BrowserSession(owner.page, "playwright", owner)
        else:
            session = BrowserSession.open("selenium")
        session.set_timeout(3)
    except Exception as error:
        pytest.skip(f"local browser is unavailable: {type(error).__name__}")
    try:
        yield session
    finally:
        session.close()


def run_task(browser, site, steps, success, **extra):
    task = TaskSpec(goal="Exercise the local demo", start_url=site, steps=steps, success=success,
                    backend=browser.backend, action_timeout=2, **extra)
    return AgentRunner(task, browser=browser).run()


def test_fill_form_and_verify(browser, local_site):
    report = run_task(browser, local_site, [AgentAction("fill", "#name", "Ada"),
                                         AgentAction("click", "#submit")],
                      [SuccessCondition("text_contains", value="Hello Ada", selector="#result")])
    assert report.status == "success", report.to_dict()
    assert len(report.steps) == 2
    assert "Ada" not in json.dumps(report.to_dict())


def test_cross_page_search_extract(browser, local_site):
    report = run_task(browser, local_site, [AgentAction("click", "#search"), AgentAction("fill", "#query", "book"),
                                         AgentAction("click", "#find")],
                      [SuccessCondition("url_contains", value="/details"),
                       SuccessCondition("extracted_equals", key="answer", value="42")], extract={"answer": "#answer"})
    assert report.status == "success", report.to_dict()
    assert report.extracted == {"answer": "42"}


def test_iframe_observation_and_operations(browser, local_site):
    report = run_task(browser, local_site, [AgentAction("fill", "#message", "demo", frame="#frame"),
                                         AgentAction("click", "#send", frame="#frame")],
                      [SuccessCondition("text_contains", value="sent", selector="#reply", frame="#frame")])
    assert report.status == "success", report.to_dict()
    observation = browser.observe()
    assert observation["frames"]
    assert any(item["tag"] == "input" for item in observation["frames"][0]["elements"])
    assert "value" not in observation["elements"][0]


def test_dynamic_dom_and_ambiguity(browser, local_site):
    browser.perform(AgentAction("navigate", value=local_site))
    script = "setTimeout(() => { const b=document.createElement('button'); b.id='late'; b.textContent='Late'; "
    script += "document.body.appendChild(b); }, 100)"
    if browser.backend == "selenium":
        browser.driver.execute_script(script)
    else:
        browser.driver.evaluate("() => {" + script + "}")
    browser.perform(AgentAction("wait", "#late"))
    assert browser.visible("#late")
    with pytest.raises(AgentError, match="multiple"):
        browser.perform(AgentAction("click", "button"))


def test_xhr_and_spa_waits(browser, local_site):
    browser.perform(AgentAction("navigate", value=local_site))
    wait_for_fetch_idle(browser.driver, quiet_for=0, timeout=1)
    script = "const x=new XMLHttpRequest(); x.open('GET','/frame'); x.send(); history.pushState({},'', '/route');"
    if browser.backend == "selenium":
        browser.driver.execute_script(script)
    else:
        browser.driver.evaluate("() => {" + script + "}")
    wait_for_fetch_idle(browser.driver, quiet_for=0.05, timeout=2)
    wait_for_spa_route_stable(browser.driver, quiet_for=0.05, timeout=2)
    assert browser.url.endswith("/route")


def test_failure_screenshot_is_masked(browser, local_site, tmp_path):
    browser.perform(AgentAction("navigate", value=local_site))
    browser.perform(AgentAction("fill", "#password", "never-show-me"))
    browser.screenshot(tmp_path / "masked.png", {"never-show-me"})
    assert (tmp_path / "masked.png").stat().st_size > 100
    assert browser.visible("#password")  # masking restores the caller's page


def test_mcp_observe_and_step_real_browser(browser, local_site, monkeypatch):
    from je_web_runner.mcp_server.server import make_default_server
    from je_web_runner.mcp_server import agent_tools
    browser.perform(AgentAction("navigate", value=local_site))
    monkeypatch.setattr(agent_tools, "_borrow", lambda backend: BrowserSession(browser.driver, browser.backend))
    server = make_default_server()
    observed = server.handle({"id": 1, "method": "tools/call", "params": {
        "name": "webrunner_observe_page", "arguments": {"backend": browser.backend},
    }})["result"]
    assert observed["isError"] is False
    assert any(item["tag"] == "button" for item in observed["structuredContent"]["elements"])
    clicked = server.handle({"id": 2, "method": "tools/call", "params": {
        "name": "webrunner_agent_step", "arguments": {"backend": browser.backend,
                                                      "action": {"kind": "click", "selector": "#search"}},
    }})["result"]
    assert clicked["isError"] is False
    assert clicked["structuredContent"]["observation"]["url"].endswith("/search")


def test_cli_real_local_task(local_site, tmp_path):
    task = {"goal": "Submit a local form", "start_url": local_site,
            "steps": [{"kind": "click", "selector": "#submit"}],
            "success": [{"kind": "text_contains", "selector": "#result", "value": "Hello"}]}
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps(task), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", WEBRUNNER_LOG_PATH=str(tmp_path / "agent.log"))
    result = subprocess.run([sys.executable, "-m", "je_web_runner", "--agent-task", str(task_path),
                             "--report", str(tmp_path / "run")],
                            capture_output=True, text=True, encoding="utf-8", timeout=45, env=env, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "success"
    assert (tmp_path / "run.agent.html").is_file()


@pytest.mark.parametrize("example", ["agent_form.json", "agent_search.json", "agent_iframe.json"])
def test_documented_examples_run_without_a_model(browser, local_site, example):
    path = Path(__file__).resolve().parents[2] / "examples" / example
    task = json.loads(path.read_text(encoding="utf-8"))
    task["start_url"] = local_site + "/index.html"
    task["backend"] = browser.backend
    report = AgentRunner(TaskSpec.from_dict(task), browser=browser).run()
    assert report.status == "success", report.to_dict()


def test_optional_real_local_model(browser, local_site):
    model = os.environ.get("WEBRUNNER_LOCAL_MODEL")
    if not model:
        pytest.skip("set WEBRUNNER_LOCAL_MODEL to opt into a real, installed local model")
    task = TaskSpec(goal="Click the Search link", start_url=local_site, backend=browser.backend,
                    planner="ollama", model=model, success=[SuccessCondition("url_contains", value="/search")])
    with_model = OllamaPlanner(task)
    try:
        report = AgentRunner(task, browser=browser, planner=with_model).run()
        assert report.status == "success", report.to_dict()
    finally:
        with_model.close()
