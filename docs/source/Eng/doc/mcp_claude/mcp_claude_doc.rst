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
speaks the stateless ``2026-07-28`` revision (a request whose
``params._meta`` names its protocol version is served without
``initialize``; ``server/discover`` reports the versions and
capabilities) and the handshake revisions ``2025-11-25``,
``2025-06-18``, ``2025-03-26`` and ``2024-11-05`` (``initialize``
answers with the client's version when it is one of these, otherwise
with ``2025-11-25``) over
**newline-delimited JSON over stdio** — every line is one JSON-RPC
message — so any client
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
          "args": ["-m", "je_web_runner.mcp_server"]
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

To use it in every project, add it at user scope instead:
``claude mcp add --scope user webrunner -- python -m je_web_runner.mcp_server``
(Claude Code stores user-scope servers in ``~/.claude.json``). Restart
Claude Code and run ``/mcp`` to confirm the server connects.

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
  record, failed}``.

* **Extract a Page Object.** *"Run ``webrunner_pom_from_html`` on the
  attached login page HTML and produce a ``LoginPage`` Python module."*

For browser tools, the server is **stateful inside the process**:
calling ``WR_get_webdriver_manager`` once creates the driver, and
subsequent ``webrunner_run_actions`` calls reuse it until you issue
``WR_quit``.

----

Tool catalog
============

The server registers 22 tools out of the box. Use
``webrunner_list_commands`` for the *full* runtime command list (every
``WR_*`` registered in the action executor, 466 of them).

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
  browser. Returns ``{stdout, record, failed}``; ``failed`` lists the
  record keys of the actions that raised, and the result's ``isError``
  is true when there is any.
* ``webrunner_run_action_files`` — Read JSON action files from disk
  and run them sequentially. Returns ``{stdout, records, failed}`` with
  one ``failed`` list per file.
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

``Tool`` also takes ``title``, ``annotations`` (for example
``je_web_runner.mcp_server._types.READ_ONLY``) and ``output_schema``;
they are sent in ``tools/list`` only when set. Before a handler runs, the
server checks the arguments against ``input_schema`` (``type``,
``required``, ``properties``, ``additionalProperties: false``, one level
of ``items.type``) and answers a mismatch with an ``isError`` result. A
handler that returns a dict gets it sent as ``structuredContent`` as well
as text; return ``ToolResult(value, is_error=True)`` to report a failure
without raising.

----

Security
========

An MCP client is a model acting on text it has read, so the run tools refuse
the commands that would widen its powers, including inside nested action
lists (``WR_execute_action``, ``WR_execute_files``):

* ``WR_add_package_to_executor`` and ``WR_add_package_to_callback_executor``,
  which import any Python package and expose its functions (``os``,
  ``subprocess`` …);
* ``WR_set_allow_arbitrary_script``, which would re-open a script gate the
  operator closed.

A refused command is reported like any failed action: the result has
``isError: true`` and the command under ``failed``.

Two environment variables, set in the client's server entry (``env``):

* ``WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS=1`` lifts the refusal, for a trusted
  client that needs to load its own helper package.
* ``WEBRUNNER_MCP_ROOT=<dir>`` limits ``webrunner_run_action_files`` and
  ``webrunner_compute_trend`` to files inside ``<dir>`` (``..`` and symlinks
  are resolved first). Unset, they read any path the process can.

----

Troubleshooting
===============

* **Claude says "no tools registered"** — confirm the server starts
  manually (``python -m je_web_runner.mcp_server`` should not exit
  immediately) and check the configured ``command`` / ``args`` resolve
  on the client's ``PATH``.
* **Stray output** — the server keeps the real stdout for protocol
  messages only (UTF-8, ``\n`` line ends) and points the process's
  stdout, including child processes, at stderr. Prints made during a
  browser tool call are captured and returned in the ``stdout`` field.
* **A tool call fails** — failures come back as a normal result with
  ``isError: true`` and the error text, not as a JSON-RPC error. Only
  an unknown tool name or non-object ``arguments`` is a protocol error
  (``-32602``).
* **JSON not serialisable** — browser tools convert
  ``WebDriver`` / ``WebElement`` instances to ``repr()`` strings via
  ``_serialize_value``. Custom return types must be JSON-friendly or
  reduce cleanly under that helper.
* **Protocol mismatch** — WebRunner speaks ``2026-07-28`` and the
  handshake revisions ``2025-11-25`` to ``2024-11-05``. A handshake
  client that asks for another version gets ``2025-11-25`` back and
  decides whether it can continue; a stateless request naming another
  version gets error ``-32022`` with the supported versions in ``data``.

----

See also
========

* :doc:`../integrations/integrations_doc` — Recorder, CI, JIRA / Slack
  notifiers, and the overview of MCP and the action JSON LSP.
* `Anthropic MCP spec <https://modelcontextprotocol.io>`_ — the
  upstream protocol reference.
