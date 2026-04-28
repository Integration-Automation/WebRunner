==================================
Using WebRunner with Claude (MCP)
==================================

WebRunner ships a **Model Context Protocol (MCP) server** that exposes
its action authoring helpers and a curated subset of its browser-driving
``WR_*`` actions to any MCP-aware client. This guide walks through
wiring the server into Claude Code, the Claude Desktop app, and other
clients, plus the full tool catalog.

.. contents:: On this page
   :local:
   :depth: 2

----

What is MCP?
============

The Model Context Protocol is a JSON-RPC 2.0 wire protocol Anthropic
uses to give Claude controlled access to local tools. WebRunner
implements protocol version ``2024-11-05`` over **newline-delimited
JSON over stdio** — every line is one JSON-RPC message — so any client
that speaks MCP stdio can drive WebRunner without HTTP, sockets, or
custom glue.

The server entry point is::

    python -m je_web_runner.mcp_server

It registers two tool families on startup:

* **Default helpers** (``build_default_tools``) — pure-Python action
  authoring, linting, locator scoring, PII redaction, sharding,
  templating, etc. No browser is launched.
* **Browser tools** (``build_browser_tools``) — drive a real browser
  through the WebRunner action executor.

If a tool name above appears in a configured client, you can call it
straight from a chat with Claude.

----

Quick start
===========

1. Install WebRunner with browser support::

       pip install je_web_runner

2. Confirm the server starts::

       python -m je_web_runner.mcp_server

   It will block on stdin reading; press *Ctrl-C* to exit.

3. Wire the server into your client (next two sections).

4. In a new Claude conversation, ask:

       "List the WebRunner MCP tools you can see."

   Claude should call ``tools/list`` and respond with the registered
   tools.

----

Configuring Claude Desktop
==========================

Claude Desktop reads MCP servers from
``claude_desktop_config.json``:

* **macOS** — ``~/Library/Application Support/Claude/claude_desktop_config.json``
* **Windows** — ``%APPDATA%\Claude\claude_desktop_config.json``

Add a ``webrunner`` entry under ``mcpServers``:

.. code-block:: json

    {
      "mcpServers": {
        "webrunner": {
          "command": "python",
          "args": ["-m", "je_web_runner.mcp_server"],
          "env": {
            "WEBRUNNER_HEADLESS": "1"
          }
        }
      }
    }

Quit and relaunch Claude Desktop; the WebRunner tools appear in the
*Tools* drawer.

.. tip::

   On Windows, prefer the absolute path to ``python.exe`` from the
   virtualenv where ``je_web_runner`` is installed
   (e.g. ``C:\\Users\\you\\.venvs\\webrunner\\Scripts\\python.exe``).
   Claude Desktop runs without the user shell, so ``PATH`` may not
   resolve a generic ``python``.

----

Configuring Claude Code (CLI)
=============================

Claude Code (the terminal client) configures MCP servers per-project
in ``.mcp.json`` next to your repo root:

.. code-block:: json

    {
      "mcpServers": {
        "webrunner": {
          "command": "python",
          "args": ["-m", "je_web_runner.mcp_server"]
        }
      }
    }

Or globally in ``~/.claude/mcp.json``. Restart Claude Code and run
``/mcp`` to confirm the server connects.

If a tool needs the action JSON to live somewhere Claude can read,
keep your action files inside the project directory — Claude Code's
file allow-list is repo-scoped by default.

----

Using WebRunner tools from a Claude conversation
================================================

Once configured, Claude can call MCP tools the same way it calls
built-in tools. Practical examples:

* **Lint an action draft.** Paste a JSON action list and ask Claude
  to *"call ``webrunner_lint_action`` and report any issues."* Claude
  receives a structured ``[{rule, severity, message, location}, ...]``
  array and summarises it.

* **Score locator strength.** *"For each step in this action list,
  rate the locator quality with ``webrunner_score_action_locators``
  and propose a stronger replacement where the score is below 60."*

* **Drive a browser.** *"Use ``webrunner_run_actions`` to open
  example.com in a Playwright session and fill the search box."*
  Claude composes the ``[command, params]`` payload, the executor
  runs against a real browser, and Claude reads back ``{stdout,
  record}``.

* **Extract a Page Object.** *"Run ``webrunner_pom_from_html`` on the
  attached login page HTML and produce a ``LoginPage`` Python module."*

For browser tools, the server is **stateful inside the process**:
calling ``WR_get_webdriver_manager`` once creates the driver, and
subsequent ``webrunner_run_actions`` calls reuse it until you issue
``WR_quit``.

----

Tool catalog
============

The server registers ~22 tools out of the box. Use
``webrunner_list_commands`` for the *full* runtime command list (every
``WR_*`` registered in the action executor — typically ~200 entries).

Authoring & lint
----------------

* ``webrunner_lint_action`` — Lint an action JSON list and report
  issues; returns ``[{rule, severity, message, location}, …]``.
* ``webrunner_score_action_locators`` — Score every locator referenced
  by an action list on a 0–100 scale.
* ``webrunner_locator_strength`` — Score a single
  ``(strategy, value)`` locator.
* ``webrunner_format_actions`` — Canonical-order action JSON.
* ``webrunner_parse_markdown`` — Transpile a Markdown bullet list
  into a ``WR_*`` action list.
* ``webrunner_render_template`` — Render a registered action template
  with parameters.

Code generation
---------------

* ``webrunner_pom_from_html`` — Discover ``[data-testid]`` / ``id`` /
  form fields and render a Python Page Object module.
* ``webrunner_translate_actions_to_playwright`` — Rewrite a ``WR_*``
  action list to its ``WR_pw_*`` Playwright equivalent.
* ``webrunner_translate_python_to_playwright`` — Static rewrite of
  Selenium-style Python source into Playwright equivalents with
  per-line diffs.

Quality & triage
----------------

* ``webrunner_a11y_diff`` — Diff two ``axe-core`` violations arrays
  into added / resolved / persisting / regressed.
* ``webrunner_cluster_failures`` — Group failures by normalised error
  signature.
* ``webrunner_compute_trend`` — Pass-rate / duration trend from a
  ledger file.

Security
--------

* ``webrunner_scan_pii`` — Detect email / phone / Luhn-card / SSN /
  ROC-ID / IPv4 in text.
* ``webrunner_redact_pii`` — Replace each match with a sentinel
  string.

Reporting & contract
--------------------

* ``webrunner_summary_markdown`` — Build a PR summary in Markdown
  from totals.
* ``webrunner_validate_response`` — Validate JSON against a minimal
  JSON-Schema; returns ``{valid, errors}``.

Sharding & infra
----------------

* ``webrunner_diff_shard`` — Pick changed action files from
  candidate / changed lists.
* ``webrunner_render_k8s`` — Render Kubernetes Job manifests for
  shard parallelism.
* ``webrunner_partition_shard`` — Deterministic SHA-1 mod-N file
  partitioning.

Browser execution
-----------------

* ``webrunner_run_actions`` — Execute an action list against a real
  browser. Returns ``{stdout, record}``.
* ``webrunner_run_action_files`` — Read JSON action files from disk
  and run them sequentially.
* ``webrunner_list_commands`` — Discover every ``WR_*`` command
  currently registered in the executor.

----

Registering custom tools
========================

External code can extend the server by calling ``McpServer.register``:

.. code-block:: python

    from je_web_runner.mcp_server import McpServer, build_default_tools
    from je_web_runner.mcp_server.server import Tool

    def my_tool(arguments):
        return {"echo": arguments.get("text", "")}

    server = McpServer()
    for tool in build_default_tools():
        server.register(tool)

    server.register(Tool(
        name="my_echo",
        description="Echo a string back.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        handler=my_tool,
    ))

    from je_web_runner.mcp_server.server import serve_stdio
    serve_stdio(server=server)

Save the script as ``my_mcp.py`` and point your client's ``command`` /
``args`` at it instead of ``python -m je_web_runner.mcp_server``.

----

Troubleshooting
===============

* **Claude says "no tools registered"** — confirm the server starts
  manually (``python -m je_web_runner.mcp_server`` should not exit
  immediately) and check the configured ``command`` / ``args`` resolve
  on the client's ``PATH``.
* **Browser tools hang** — the browser tools use the WebRunner
  executor, which prints to stdout. The server captures stdout and
  surfaces it in the ``stdout`` field; if a callback writes directly
  to ``sys.__stdout__`` it can corrupt the wire. Avoid raw prints in
  callbacks.
* **JSON not serialisable** — browser tools convert
  ``WebDriver`` / ``WebElement`` instances to ``repr()`` strings via
  ``_serialize_value``. Custom return types must be JSON-friendly or
  reduce cleanly under that helper.
* **Protocol mismatch** — WebRunner advertises
  ``protocolVersion=2024-11-05``. Newer clients negotiate down; if
  yours doesn't, pin the client to that version.

----

See also
========

* :doc:`../integrations/integrations_doc` — Recorder, CI, JIRA / Slack
  notifiers, and the overview of MCP and the action JSON LSP.
* `Anthropic MCP spec <https://modelcontextprotocol.io>`_ — the
  upstream protocol reference.
