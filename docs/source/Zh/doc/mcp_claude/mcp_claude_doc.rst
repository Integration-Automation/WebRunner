============================================
搭配 Claude 使用 WebRunner (MCP)
============================================

WebRunner 內建 **Model Context Protocol (MCP) server**,把 action 撰寫
工具與部分 ``WR_*`` 瀏覽器動作開放給任何支援 MCP 的客戶端。本章說明
如何把 server 接到 Claude Code、Claude Desktop 與其他客戶端,並列出完整
工具表。

.. contents:: 本頁目錄
   :local:
   :depth: 2

----

什麼是 MCP?
===========

Model Context Protocol 是 Anthropic 用來讓 Claude 安全呼叫本機工具的
JSON-RPC 2.0 協定。WebRunner 實作 ``2024-11-05`` 版本,
透過 **stdio 上的 newline-delimited JSON** (每行一個 JSON-RPC 訊息)
通訊,因此任何支援 MCP stdio 的客戶端都能直接驅動 WebRunner,
不需 HTTP、socket 或自訂橋接。

啟動指令::

    python -m je_web_runner.mcp_server

server 啟動時會註冊兩組工具:

* **Default helpers** (``build_default_tools``) — 純 Python 的 action
  撰寫、lint、locator 評分、PII 遮罩、sharding、模板等,**不會**啟動
  瀏覽器。
* **Browser tools** (``build_browser_tools``) — 透過 WebRunner action
  executor 操作真實瀏覽器。

凡是已註冊的工具,Claude 都能在對話中直接呼叫。

----

快速上手
========

1. 安裝 WebRunner::

       pip install je_web_runner

2. 確認 server 啟得起來::

       python -m je_web_runner.mcp_server

   會卡在讀取 stdin,按 *Ctrl-C* 結束即可。

3. 把 server 設定到客戶端(下兩節)。

4. 在 Claude 對話中問:

       "列出你看得到的 WebRunner MCP 工具。"

   Claude 會呼叫 ``tools/list`` 並回覆已註冊的工具清單。

----

設定 Claude Desktop
===================

Claude Desktop 從 ``claude_desktop_config.json`` 讀取 MCP server:

* **macOS**:``~/Library/Application Support/Claude/claude_desktop_config.json``
* **Windows**:``%APPDATA%\Claude\claude_desktop_config.json``

在 ``mcpServers`` 下新增 ``webrunner`` 條目:

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

關閉並重開 Claude Desktop,WebRunner 工具就會出現在 *Tools* 抽屜。

.. tip::

   Windows 上建議直接寫安裝 ``je_web_runner`` 那個 venv 的
   ``python.exe`` 絕對路徑(例如
   ``C:\\Users\\you\\.venvs\\webrunner\\Scripts\\python.exe``),
   因為 Claude Desktop 不會載入使用者 shell 的 ``PATH``,
   通用的 ``python`` 不一定能解析到。

----

設定 Claude Code (CLI)
======================

Claude Code(終端機客戶端)以專案為單位,從 repo 根目錄的
``.mcp.json`` 讀取 MCP server 設定:

.. code-block:: json

    {
      "mcpServers": {
        "webrunner": {
          "command": "python",
          "args": ["-m", "je_web_runner.mcp_server"]
        }
      }
    }

或寫到全域的 ``~/.claude/mcp.json``。重啟 Claude Code 後執行 ``/mcp``
確認 server 連得上。

如果工具會讀寫 action JSON,請把檔案放在專案目錄內 — Claude Code
預設只允許 repo 範圍內的檔案存取。

----

在對話中使用 WebRunner 工具
===========================

設定完成後,Claude 呼叫 MCP 工具就跟內建工具一樣自然。常見用法:

* **Lint 一份 action 草稿。** 貼一段 action JSON,然後請 Claude
  *「呼叫 ``webrunner_lint_action`` 並整理問題清單。」* Claude 會收到
  ``[{rule, severity, message, location}, ...]``,再幫你摘要。

* **評估 locator 強度。** *「對這份 action list,用
  ``webrunner_score_action_locators`` 評分,並把分數低於 60 的步驟
  改寫成更穩定的 locator。」*

* **驅動瀏覽器。** *「用 ``webrunner_run_actions`` 開啟 example.com,
  在搜尋欄輸入文字。」* Claude 會組好 ``[command, params]`` payload,
  executor 在真實瀏覽器執行,Claude 再讀回 ``{stdout, record}``。

* **產生 Page Object。** *「用 ``webrunner_pom_from_html`` 把附上的
  登入頁 HTML 轉成 ``LoginPage`` Python 模組。」*

對於 browser tools,server **在同一個 process 內保持狀態**:呼叫一次
``WR_get_webdriver_manager`` 建立 driver 後,後續的
``webrunner_run_actions`` 都會重用,直到呼叫 ``WR_quit``。

----

工具清單
========

server 預設註冊約 22 個工具。完整 runtime 指令清單(executor 中所有
``WR_*``,通常約 200 個)請呼叫 ``webrunner_list_commands``。

撰寫與 lint
-----------

* ``webrunner_lint_action`` — 對 action JSON list 跑 lint,回傳
  ``[{rule, severity, message, location}, …]``。
* ``webrunner_score_action_locators`` — 對 action list 中每個 locator
  評分(0–100)。
* ``webrunner_locator_strength`` — 對單一 ``(strategy, value)`` 評分。
* ``webrunner_format_actions`` — 用一致的順序輸出 action JSON。
* ``webrunner_parse_markdown`` — 把 Markdown 列表轉成 ``WR_*`` action。
* ``webrunner_render_template`` — 套用已註冊的 action 模板與參數。

程式碼生成
----------

* ``webrunner_pom_from_html`` — 從 HTML 找出 ``[data-testid]`` /
  ``id`` / 表單欄位,生成 Page Object Python 模組。
* ``webrunner_translate_actions_to_playwright`` — 把 ``WR_*`` action
  list 改寫成 ``WR_pw_*`` Playwright 版本。
* ``webrunner_translate_python_to_playwright`` — 靜態翻譯
  Selenium 風格 Python 為 Playwright,並回傳逐行 diff。

品質與 triage
-------------

* ``webrunner_a11y_diff`` — 對兩份 axe-core violations 做 diff,
  分為 added / resolved / persisting / regressed。
* ``webrunner_cluster_failures`` — 依錯誤特徵 cluster 失敗。
* ``webrunner_compute_trend`` — 從 ledger 算 pass-rate / 時長趨勢。

安全
----

* ``webrunner_scan_pii`` — 偵測 email / 電話 / Luhn 卡號 / SSN /
  ROC ID / IPv4。
* ``webrunner_redact_pii`` — 對偵測到的字串遮罩成 sentinel。

報告與 contract
---------------

* ``webrunner_summary_markdown`` — 由統計值生成 PR Markdown 摘要。
* ``webrunner_validate_response`` — 用最小 JSON-Schema 驗證 JSON,
  回傳 ``{valid, errors}``。

Sharding 與 infra
-----------------

* ``webrunner_diff_shard`` — 從候選 / 變更檔案中挑出需要重跑的。
* ``webrunner_render_k8s`` — 產生 Kubernetes Job manifest。
* ``webrunner_partition_shard`` — SHA-1 mod-N 的決定性檔案分配。

瀏覽器執行
----------

* ``webrunner_run_actions`` — 對真實瀏覽器執行 action list,回傳
  ``{stdout, record}``。
* ``webrunner_run_action_files`` — 讀檔並依序執行 action JSON 檔。
* ``webrunner_list_commands`` — 列出 executor 目前註冊的所有
  ``WR_*`` 指令。

----

註冊自訂工具
============

外部程式可透過 ``McpServer.register`` 擴充 server:

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

把上面這段存成 ``my_mcp.py``,並把客戶端的 ``command`` / ``args`` 改指
這個檔(取代 ``python -m je_web_runner.mcp_server``)即可。

----

疑難排解
========

* **Claude 顯示「沒有可用的工具」** — 先手動執行
  ``python -m je_web_runner.mcp_server`` 確認 server 沒立刻退出,
  並檢查設定中的 ``command`` / ``args`` 在客戶端的 ``PATH`` 下解析得到。
* **Browser tools 卡住不動** — Browser tools 透過 executor 執行,
  executor 會 print 到 stdout。Server 已經把 stdout 重新導向到 buffer
  並放在回傳的 ``stdout`` 欄位;但若 callback 直接寫
  ``sys.__stdout__`` 仍會破壞 wire,務必避免在 callback 中 raw print。
* **JSON 無法序列化** — Browser tools 透過 ``_serialize_value`` 把
  ``WebDriver`` / ``WebElement`` 轉成 ``repr()`` 字串。自訂回傳值若不是
  JSON-friendly,需要在該 helper 下能 reduce。
* **Protocol 版本不合** — WebRunner 公告 ``protocolVersion=2024-11-05``,
  較新的客戶端會自動 negotiate down;若不行請把客戶端鎖定在這版。

----

延伸閱讀
========

* :doc:`../integrations/integrations_doc` — Recorder、CI、JIRA / Slack
  通知、以及 MCP 與 action JSON LSP 的概觀。
* `Anthropic MCP 規格 <https://modelcontextprotocol.io>`_ — 上游協定
  參考。
