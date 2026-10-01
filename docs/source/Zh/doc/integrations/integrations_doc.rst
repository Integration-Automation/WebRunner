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
  第一個失敗就停止；
* ``WR_ac_fill_native_file_dialog(file_path, submit=True, wait_seconds=1)``：
  在作業系統的開啟或儲存對話框輸入路徑（轉成絕對路徑），``submit`` 不為
  false 時再按 Enter；
* ``WR_ac_assert_image_on_screen(image_path, detect_threshold=None)``：螢幕上
  找不到範本圖片就失敗；回傳其中心 ``[x, y]``；
* ``WR_ac_click_element_native(selector=None, by="css selector",
  mouse_button="mouse_left", scale=None)``：用真正的滑鼠點擊元素（沒給
  ``selector`` 就是目前元素），是受信任的點擊而不是 WebDriver 的。元素先捲到
  viewport 中央，再用視窗的 ``screenX/Y``、外框與內部尺寸以及
  ``devicePixelRatio`` 把中心換算到螢幕；沒給 ``scale`` 時顯示縮放取
  ``devicePixelRatio``，頁面縮放 100 % 時正確。視窗不能被遮住；
* ``WR_ac_basic_auth(username_env, password_env, url=None, submit=True,
  wait_seconds=1)``：用兩個環境變數裡的帳密（傳的是變數名稱，不是值）回答
  瀏覽器的 HTTP 基本認證對話框。給 ``url`` 時先確認頁面握有鍵盤焦點
  （AutoControl 打字會送到最前面的視窗），再開始開啟該頁、不等待，因為
  對需要基本認證的頁面做傳統的 ``get`` 會在對話框開著時一直等；接著透過
  AutoControl 的 ``AC_write_secret`` 輸入帳號、Tab、密碼與 Enter，字元一字
  不差，也不會進入它的 log、紀錄或回傳值。需要有 ``AC_write_secret`` 的
  ``je_auto_control``；Playwright 請用 ``WR_pw_set_context_options`` 的
  ``http_credentials``。

原生命令會拒絕視窗不在這台機器螢幕上的 Selenium driver：headless
瀏覽器，或遠端的（grid 或裝置雲）。Playwright 瀏覽器不會被檢查，因為
Playwright 不回報它是否以 headless 啟動：請以 ``headless=False`` 啟動。

AutoControl 動作失敗時，它所在的 ``WR_ac_*`` 動作以 ``AutoControlBridgeError``
失敗。橋接會拒絕 shell 命令與程式（``AC_shell_command``、
``AC_execute_process``）、載入套件（``AC_add_package_*``）、動作清單與檔案
（``AC_execute_action``、``AC_execute_files``）、``AC_run_agent``，以及回頭
呼叫 WebRunner 的 ``AC_web_*``；這些名稱出現在動作的任何位置都會被拒絕，
包括迴圈本體與以 JSON 字串傳入的本體。除非設
``WEBRUNNER_MCP_ALLOW_UNSAFE_COMMANDS=1``，MCP server 會拒絕
``WR_ac_available``、``WR_ac_list_commands`` 以外的每個 ``WR_ac_*`` 命令。

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
