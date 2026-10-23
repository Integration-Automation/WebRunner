Local browser agents
====================

Tasks run through Python, CLI or MCP, using Selenium by default or the optional
Playwright backend. Fixed steps need no model. Autonomous planning uses an
explicitly installed, open-source local Ollama model. No subscription, API key,
cloud inference, model download or paid fallback is used by the runner.

Quick start without a model
---------------------------

Install Chrome and its compatible driver before running offline. Playwright users
also install ``playwright`` and its browser binaries using
``python -m playwright install chromium``. Serve the included demo in one terminal:

.. code-block:: bash

    python -m http.server 8000 --bind 127.0.0.1 --directory examples/agent_demo

Run a task in another terminal:

.. code-block:: bash

    python -m je_web_runner --agent-task examples/agent_form.json --report results/form
    python -m je_web_runner --agent-task examples/agent_search.json --report results/search
    python -m je_web_runner --agent-task examples/agent_iframe.json --report results/frame

The exit status is 0 only when all deterministic success conditions pass; failure,
timeout and incomplete tasks return 1. ``--agent-task`` is independent of legacy
execution flags; ``--report`` writes ``BASE.agent.json`` and standalone, escaped
``BASE.agent.html``. Failure screenshots go into ``BASE.agent-artifacts``.
Set ``"backend": "playwright"`` in the task to use Playwright.

Python
------

.. code-block:: python

    import json
    from pathlib import Path
    from je_web_runner.api.ai import run_agent

    task = json.loads(Path("examples/agent_search.json").read_text(encoding="utf-8"))
    report = run_agent(task, artifact_dir="results/search-artifacts")
    print(report.status, report.extracted)

``TaskSpec``, ``AgentAction``, ``SuccessCondition``, ``AgentRunner`` and
``AgentReport`` are available from ``je_web_runner.api.ai``. Injecting a
``BrowserSession`` into ``AgentRunner`` borrows the caller's browser without
closing it. The default runner creates an isolated wrapper, leaving the legacy
browser singletons alone. One agent operation runs per process; use separate
processes for concurrent tasks.

Task contract
-------------

The task schema is ``docs/reference/webrunner-agent-schema.json``. ``goal``,
absolute HTTP(S) ``start_url`` and nonempty ``success`` are required. All success
conditions must pass: ``url_contains`` uses ``value``; ``visible`` uses
``selector``; ``text_contains`` uses ``value`` and an optional ``selector``
(default ``body``); ``extracted_equals`` compares ``key`` against ``value``.
An optional ``extract`` mapping reads named fields from unique visible elements.

``planner`` defaults to ``steps``. Actions support ``navigate``, ``click``,
``fill``, ``select`` (option value), ``check``, ``scroll`` (down by default,
``value: "up"`` for up), ``wait``, ``extract`` (requires ``key``) and ``done``.
Selectors are CSS; ``frame`` selects one iframe. The observer includes the main
document and up to ten visible iframes, with up to 150 interactive elements per
document. It omits form values. Arbitrary JavaScript, packages and desktop actions
cannot be requested through agent actions. Closed shadow roots and nested frame
chains are outside this agent interface; existing WebRunner traversal helpers remain.

Default limits are 25 steps, 300 seconds total and 15 seconds per browser operation.
``max_steps``, ``timeout`` and ``action_timeout`` can override them. Three consecutive
identical action/page-state proposals stop the run. Failed clicks/submissions are
never automatically retried. A model's ``done`` response cannot declare success.
The deadline is checked between operations, whose own timeouts bound blocking calls;
this is not a process-level hard kill of a stalled browser driver.

Local autonomous planning
-------------------------

Install Ollama separately and an open-source local model whose license permits
your use and whose size fits your machine. Choose its exact installed name;
the package intentionally supplies no model or automatic download.
Disable cloud features with ``OLLAMA_NO_CLOUD=1`` and restart the Ollama service.
The runner checks ``/api/status`` for cloud-disabled mode and ``/api/tags`` for
local weights, rejecting remote model entries. Older services without this status
endpoint must be updated. See https://docs.ollama.com/faq and
https://docs.ollama.com/capabilities/structured-outputs.

Change a task to ``"planner": "ollama"`` and ``"model": "YOUR_INSTALLED_MODEL"``;
omit ``steps``. The local model receives the goal, success conditions, a bounded
page observation and recent step history, and returns one schema-constrained action.
Malformed output receives one correction attempt. Missing models, disabled service
or invalid responses fail explicitly. The connector uses loopback HTTP, ignores
proxy environment settings, refuses redirects and has no cloud fallback.

Use ``${ENV.NAME}`` in action values and explicitly list ``NAME`` in ``allowed_env``
for secrets. Environment values resolve immediately before execution. Fill values,
allowed environment secrets and credential URL parameters are redacted from reports
and model observations. Failure screenshots hide controls, iframe contents, shadow
hosts and known secret text. Hardware, electricity and initial software/model
downloads remain the responsibility of the local environment.

MCP
---

The default server includes three agent tools:

* ``webrunner_observe_page`` reads the active backend's page.
* ``webrunner_agent_step`` performs one typed action and returns a fresh observation.
* ``webrunner_run_agent`` runs a TaskSpec in its own browser and returns AgentReport;
  ``isError`` is true unless the outcome is verified success.

Observation/step tools borrow a browser started by ``webrunner_run_actions`` and
accept ``backend``. The run tool accepts ``task``. MCP caps tasks at 100 steps,
300 total seconds and 15 seconds per operation. Only environment names configured
by the server host in ``WEBRUNNER_AGENT_ALLOWED_ENV`` (comma separated) are available;
a task cannot grant itself access. The existing MCP script/package restrictions
remain in place. Reports from MCP are structured content; no arbitrary output path
is accepted by these tools.

Commercial integration migration
--------------------------------

BrowserStack, Sauce Labs, LambdaTest, device-cloud clients and TestRail exports and
WR commands have been removed by explicit request, as a breaking change.
Use ``je_web_runner.api.platform.start_remote_driver(hub_url, capabilities)`` or
``WR_start_remote_driver`` for a self-hosted Selenium Grid; use local Appium for
devices. Export JSON/JUnit or send a generic webhook for test results. Jira and
free notifications remain. Only a zero-service-cost local rate card ships by default;
generic estimates and scheduling remain available.

Locator healing now fails on ambiguous actionable matches and skips hidden or
disabled elements. Smart waits track fetch and XHR, reinstall hooks after navigation
and observe history/hash changes. Network idle is an explicit bounded wait, never a
prerequisite for element/URL-based agent actions, so a long-lived connection cannot
indefinitely block task progress.
