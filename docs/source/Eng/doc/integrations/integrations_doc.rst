============
Integrations
============

Recorder
========

JS-injection recorder (no CDP, cross-browser): captures click / change
events and emits a ``WR_*`` action JSON draft. Sensitive fields
(``type=password``, names matching password / card / cvv / ssn / secret /
token / api_key / otp / passcode, 13–19-digit values) are masked by
default.

CI / integrations
=================

* **GitHub Actions annotations** — ``emit_failure_annotations`` /
  ``emit_from_junit_xml`` produce ``::error file=…::`` lines.
* **JIRA / TestRail** — ``jira_create_failure_issues`` /
  ``testrail_send_results`` for post-run sync.
* **Slack / generic webhook** — ``notify_run_summary``.
* **Selenium Grid 4 docker-compose** — ``docker/docker-compose.yml`` ships
  hub + Chrome + Firefox nodes.
* **IDE configs** — ``docs/ide/vscode-settings.example.json`` and
  ``docs/ide/jetbrains-jsonschemamapping.example.xml`` wire the action JSON
  schema into VS Code / JetBrains.

AI assistance
=============

WebRunner ships **no built-in LLM client**. ``set_llm_callable(fn)``
registers any ``Callable[[str], str]`` and powers:

* ``suggest_locator(html, description)`` — last-resort locator suggestion.
* ``llm_self_heal_locator(name, html_provider)`` — pluggable hook for the
  self-healing locator flow.
* ``generate_actions_from_prompt(request)`` — natural language → action
  JSON draft.
* ``explain_failure(test_name, error_repr, console=, network=, steps=)``
  — produces a JSON RCA: ``{likely_cause, evidence, next_steps,
  confidence}``.

MCP server
==========

WebRunner ships a Model Context Protocol server so MCP-aware clients can
drive it over JSON-RPC stdio:

.. code-block:: shell

   python -m je_web_runner.mcp_server

Default tools registered (19 in total):

* Action authoring & lint: ``webrunner_lint_action``,
  ``webrunner_score_action_locators``, ``webrunner_locator_strength``,
  ``webrunner_format_actions``, ``webrunner_parse_markdown``,
  ``webrunner_render_template``,
  ``webrunner_translate_actions_to_playwright``,
  ``webrunner_translate_python_to_playwright``
* Code generation: ``webrunner_pom_from_html``
* Quality & triage: ``webrunner_a11y_diff``,
  ``webrunner_cluster_failures``, ``webrunner_compute_trend``
* Security: ``webrunner_scan_pii``, ``webrunner_redact_pii``
* Reporting & contract: ``webrunner_summary_markdown``,
  ``webrunner_validate_response``
* Sharding / infra: ``webrunner_diff_shard``,
  ``webrunner_render_k8s``, ``webrunner_partition_shard``

Custom tools register via ``McpServer.register(Tool(...))``; the server
implements MCP ``2024-11-05`` (``initialize`` / ``tools/list`` /
``tools/call`` / ``resources/list`` / ``ping`` / ``shutdown``).

Action JSON LSP
===============

.. code-block:: shell

   python -m je_web_runner.action_lsp

Standard LSP 3.17-shaped server over stdio. ``textDocument/completion``
suggests every registered ``WR_*`` command; ``textDocument/didOpen`` /
``didChange`` push ``publishDiagnostics`` based on
:func:`linter.action_linter.lint_action`.
