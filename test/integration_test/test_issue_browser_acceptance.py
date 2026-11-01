"""Real headless browser evidence on indexed HTML; container isolation has separate required acceptance."""
import copy
import socket
import sys

from je_web_runner.utils.issue_worker.browser_entry import execute_case


def test_real_browser_verifies_source_behavior_and_reports_assertion_failure(tmp_path):
    html = tmp_path / "index.html"
    html.write_text('''<input id="name"><button id="submit" onclick="document.querySelector('#result').textContent=
        'Hello '+document.querySelector('#name').value">Submit</button><p id="result">waiting</p>''', encoding="utf-8")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    task = {"server": [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                        "--directory", str(tmp_path)], "port": port, "task": {
        "goal": "Verify greeting", "start_url": f"http://127.0.0.1:{port}/index.html", "backend": "selenium",
        "timeout": 30, "action_timeout": 2,
        "steps": [{"kind": "fill", "selector": "#name", "value": "Ada"}, {"kind": "click", "selector": "#submit"}],
        "success": [{"kind": "text_contains", "selector": "#result", "value": "Hello Ada"}]}}
    report = execute_case(task, tmp_path)
    assert report["status"] == "success", report
    broken = copy.deepcopy(task)
    broken["task"]["success"][0]["value"] = "Hello never-supplied"
    report = execute_case(broken, tmp_path)
    assert report["status"] != "success"
