"""Real local HTTP exchange with a fixture model, denying external Python connections."""
import ipaddress
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from je_web_runner.utils.agent import AgentAction, AgentError, SuccessCondition, TaskSpec
from je_web_runner.utils.agent.planners import OllamaPlanner


@pytest.fixture
def ollama_fixture():
    state = {"cloud_disabled": True, "models": [{"name": "fixture-model:latest"}], "calls": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = ({"cloud": {"disabled": state["cloud_disabled"]}} if self.path == "/api/status"
                       else {"models": state["models"]})
            self.reply(payload)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["calls"].append((self.path, data))
            self.reply({"message": {"content": '{"kind":"click","selector":"#search"}'}})

        def reply(self, payload):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def planner_for(endpoint):
    task = TaskSpec(goal="Click Search", start_url="http://localhost/demo", planner="ollama", model="fixture-model",
                    success=[SuccessCondition("url_contains", value="/search")])
    return OllamaPlanner(task, endpoint)


def test_no_keys_no_external_network_no_paid_fallback(ollama_fixture, monkeypatch):
    endpoint, state = ollama_fixture
    original_connect = socket.socket.connect

    def local_connect(connection, address):
        assert ipaddress.ip_address(address[0]).is_loopback, "external connection attempted"
        return original_connect(connection, address)

    monkeypatch.setattr(socket.socket, "connect", local_connect)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OLLAMA_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    planner = planner_for(endpoint)
    try:
        planner.preflight(2)
        assert planner.plan({"title": "Local demo"}, 2) == AgentAction("click", "#search")
        assert [path for path, _payload in state["calls"]] == ["/api/chat"]
        assert state["calls"][0][1]["format"]["additionalProperties"] is False
    finally:
        planner.close()


@pytest.mark.parametrize("change", ["cloud", "weights"])
def test_unusable_local_service_never_requests_generation(ollama_fixture, change):
    endpoint, state = ollama_fixture
    if change == "cloud":
        state["cloud_disabled"] = False
    else:
        state["models"] = []
    planner = planner_for(endpoint)
    try:
        with pytest.raises(AgentError):
            planner.preflight(2)
        assert state["calls"] == []
    finally:
        planner.close()
