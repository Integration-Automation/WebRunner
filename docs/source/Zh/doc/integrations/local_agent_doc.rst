本機瀏覽器 Agent
================

透過 Python、CLI 或 MCP 執行指定任務，預設使用 Selenium，也可選用 Playwright。
固定步驟模式不需要模型；自主規劃使用明確指定、已安裝的開源本機 Ollama 模型。
執行器不使用訂閱、API 金鑰、雲端推論、自動模型下載或付費備援。

不使用模型的快速開始
--------------------

離線執行前先安裝 Chrome 及相容的驅動程式。Playwright 使用者另安裝
``playwright``，再執行 ``python -m playwright install chromium``。
先在一個終端機啟動範例站：

.. code-block:: bash

    python -m http.server 8000 --bind 127.0.0.1 --directory examples/agent_demo

再於另一個終端機執行：

.. code-block:: bash

    python -m je_web_runner --agent-task examples/agent_form.json --report results/form
    python -m je_web_runner --agent-task examples/agent_search.json --report results/search
    python -m je_web_runner --agent-task examples/agent_iframe.json --report results/frame

所有完成條件通過才回傳結束碼 0；失敗、逾時與未完成均回傳 1。
``--agent-task`` 與既有執行旗標分開使用；可搭配 ``--report``，產生
``BASE.agent.json`` 與可獨立開啟、已跳脫內容的 ``BASE.agent.html``。
失敗截圖位於 ``BASE.agent-artifacts``。任務設定
``"backend": "playwright"`` 即改用 Playwright。

Python
------

.. code-block:: python

    import json
    from pathlib import Path
    from je_web_runner.api.ai import run_agent

    task = json.loads(Path("examples/agent_search.json").read_text(encoding="utf-8"))
    report = run_agent(task, artifact_dir="results/search-artifacts")
    print(report.status, report.extracted)

``je_web_runner.api.ai`` 另提供 ``TaskSpec``、``AgentAction``、
``SuccessCondition``、``AgentRunner``、``AgentReport``。
向 ``AgentRunner`` 注入 ``BrowserSession`` 會借用瀏覽器，不會替呼叫者關閉它。
預設執行器建立獨立 wrapper，不更動既有瀏覽器 singleton。
同一程序一次只執行一個 agent 操作；平行任務使用獨立程序。

任務格式
--------

Schema 位於 ``docs/reference/webrunner-agent-schema.json``。
必要欄位為 ``goal``、完整 HTTP(S) ``start_url`` 與非空的 ``success``。
完成條件全部通過才算成功：``url_contains`` 使用 ``value``；
``visible`` 使用 ``selector``；``text_contains`` 使用 ``value`` 與選用的
``selector``（預設 ``body``）；``extracted_equals`` 比對 ``key`` 與 ``value``。
選用的 ``extract`` 字典可從唯一、可見元素讀取具名結果。

``planner`` 預設為 ``steps``。支援的動作為 ``navigate``、``click``、
``fill``、``select``（選項值）、``check``、``scroll``（預設向下，
``value: "up"`` 為向上）、``wait``、``extract``（須有 ``key``）與 ``done``。
定位器使用 CSS；``frame`` 可指定一層 iframe。
觀察器包含主文件及最多十個可見 iframe，每個文件最多 150 個互動元素，
不讀取表單值。Agent 動作不能要求任意 JavaScript、套件或桌面操作。
封閉 Shadow DOM 與多層 iframe 不屬於這個 agent 介面；既有穿透與導覽工具仍可使用。

預設最多 25 步、總時限 300 秒、每次瀏覽器操作 15 秒，可由
``max_steps``、``timeout``、``action_timeout`` 調整。
連續三次相同頁面狀態與動作提案會停止；失敗的點擊或送出不會自動重試。
模型回傳 ``done`` 不能直接宣告成功。
總時限在操作之間檢查，阻塞呼叫依操作逾時限制結束，並非由獨立程序強制終止卡住的驅動程式。

本機自主規劃
------------

另行安裝 Ollama，並選擇授權符合使用需求、大小適合本機硬體的開源模型。
須明確指定已安裝模型名稱；套件不附模型，也不自動下載。
設定 ``OLLAMA_NO_CLOUD=1`` 並重新啟動 Ollama 以關閉雲端功能。
執行器透過 ``/api/status`` 確認雲端已關閉，再由 ``/api/tags`` 確認有本機權重，
拒絕遠端模型項目。沒有狀態端點的舊版服務須先更新。
參考 https://docs.ollama.com/faq 與
https://docs.ollama.com/capabilities/structured-outputs。

任務改為 ``"planner": "ollama"``、``"model": "YOUR_INSTALLED_MODEL"``，
並省略 ``steps``。模型收到目標、完成條件、有限大小的頁面觀察與近期步驟，
每次只回傳一個受 Schema 限制的動作。格式錯誤最多修正一次。
模型不存在、服務離線或回應無效時明確失敗。
連接器只使用 loopback HTTP，忽略代理環境設定、拒絕重新導向，且沒有雲端備援。

動作值可使用 ``${ENV.NAME}``，並須在 ``allowed_env`` 明確列出 ``NAME``。
環境變數值只在執行動作前展開。填寫值、允許的環境變數密鑰及憑證 URL 參數，
均會從報告與模型觀察中遮蔽。失敗截圖隱藏表單控制項、iframe 內容、
Shadow DOM 容器及已知密鑰文字。硬體、電力及初次軟體／模型下載由本機環境提供。

MCP
---

預設伺服器新增三個工具：

* ``webrunner_observe_page``：觀察目前後端的頁面。
* ``webrunner_agent_step``：執行一個有型別限制的動作，回傳更新後的頁面觀察。
* ``webrunner_run_agent``：以獨立瀏覽器執行 TaskSpec，回傳 AgentReport；
  只有通過驗證的成功結果才會令 ``isError`` 為 false。

觀察與單步工具使用 ``backend`` 選擇後端，借用先前經
``webrunner_run_actions`` 啟動的瀏覽器；完整任務工具接受 ``task``。
MCP 上限為 100 步、總時限 300 秒、每次操作 15 秒。
可使用的環境變數必須由主機端透過 ``WEBRUNNER_AGENT_ALLOWED_ENV``
以逗號分隔設定；任務不能自行擴大權限。既有 MCP 腳本與套件限制保持有效。
MCP 報告以結構化內容回傳，這三個工具不接受任意輸出路徑。

商業整合遷移
------------

依要求移除 BrowserStack、Sauce Labs、LambdaTest、裝置雲及 TestRail 的
Python 匯出與 WR 命令，屬於明示破壞性變更。
自架 Selenium Grid 改用 ``je_web_runner.api.platform.start_remote_driver``
或 ``WR_start_remote_driver``；裝置使用本機 Appium。
結果以 JSON／JUnit 或通用 webhook 輸出。保留 Jira 與免費通知。
內建估算參數只保留本機零服務費設定；通用估算與排程仍可使用。

定位備援遇到多個可操作元素時回報歧義，並略過隱藏或停用的元素。
智慧等待追蹤 fetch／XHR、在導頁後重新注入監測，並觀察 history／hash 變化。
網路閒置是有期限的明確等待條件，不是元素／URL 型 agent 操作的必要前提，
因此長連線不會無限阻塞任務進度。
