========
外部整合
========

錄製器
======

JS 注入式錄製，跨 Chrome / Firefox / Edge。預設遮罩敏感欄位（密碼、
卡號、CVV、SSN、token、api_key 等）。

CI 與整合
=========

* GitHub Actions ``::error::`` 行內註解
* JIRA / TestRail 上報
* Slack / 通用 webhook
* Selenium Grid 4 docker-compose
* VS Code / JetBrains JSON Schema 設定範例

桌面控制（AutoControl）
==============================

``pip install je_web_runner[autocontrol]`` 會加裝 AutoControl
（``je_auto_control``），它操作真正的滑鼠、鍵盤與螢幕。WebRunner 只在下列
命令執行時才 import 它：

* ``WR_ac_available``：``je_auto_control`` 是否已安裝（只查找，不 import）；
* ``WR_ac_list_commands``：橋接會執行的 ``AC_*`` 命令；
* ``WR_ac_run``：執行一個 AutoControl 動作並回傳它的值，例如
  ``["WR_ac_run", [["AC_write", {"write_string": "hello"}]]]``；
* ``WR_ac_run_actions``：依序執行一串 AutoControl 動作並回傳各自的值；
  第一個失敗就停止。

AutoControl 動作失敗時，它所在的 ``WR_ac_*`` 動作以 ``AutoControlBridgeError``
失敗。橋接會拒絕 shell 命令與程式（``AC_shell_command``、
``AC_execute_process``）、載入套件（``AC_add_package_*``）、動作清單與檔案
（``AC_execute_action``、``AC_execute_files``）、``AC_run_agent``，以及回頭
呼叫 WebRunner 的 ``AC_web_*``；這些名稱出現在動作的任何位置都會被拒絕，
包括迴圈本體與以 JSON 字串傳入的本體。除非設
``WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS=1``，MCP server 會拒絕 ``WR_ac_run``
與 ``WR_ac_run_actions``。

AI 輔助
=======

WebRunner 不打包任何 LLM client。透過 ``set_llm_callable(fn)`` 註冊任意
``Callable[[str], str]`` 即可：

* ``suggest_locator`` — 自我修復定位的 LLM 後援
* ``generate_actions_from_prompt`` — 自然語言生成 action 草稿
* ``explain_failure`` — 從失敗素材生成 RCA：``{likely_cause, evidence,
  next_steps, confidence}``

MCP server
==========

提供 Model Context Protocol stdio JSON-RPC server：

.. code-block:: shell

   python -m je_web_runner.mcp_server

預設工具共 19 個，依用途分組：

* Action 撰寫 / lint：``webrunner_lint_action`` /
  ``webrunner_score_action_locators`` / ``webrunner_locator_strength`` /
  ``webrunner_format_actions`` / ``webrunner_parse_markdown`` /
  ``webrunner_render_template`` /
  ``webrunner_translate_actions_to_playwright`` /
  ``webrunner_translate_python_to_playwright``
* 程式碼生成：``webrunner_pom_from_html``
* 品質 / triage：``webrunner_a11y_diff`` / ``webrunner_cluster_failures``
  / ``webrunner_compute_trend``
* 安全 / 隱私：``webrunner_scan_pii`` / ``webrunner_redact_pii``
* 報告 / contract：``webrunner_summary_markdown`` /
  ``webrunner_validate_response``
* Sharding / infra：``webrunner_diff_shard`` / ``webrunner_render_k8s``
  / ``webrunner_partition_shard``

可透過 ``McpServer.register(Tool(...))`` 自行擴充工具，支援無狀態的
``2026-07-28`` 與握手版本 ``2025-11-25`` 到 ``2024-11-05``。

Action JSON LSP
===============

.. code-block:: shell

   python -m je_web_runner.action_lsp

標準 LSP 3.17 stdio server，``textDocument/completion`` 回傳所有已註冊
``WR_*`` 指令；``textDocument/didOpen`` / ``didChange`` 觸發
``publishDiagnostics`` 跑 action linter。
