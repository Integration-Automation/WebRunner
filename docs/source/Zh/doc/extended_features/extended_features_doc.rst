==================================
延伸功能
==================================

WebRunner 除了原本的 Selenium 包裝，現已附帶 Playwright backend、JSON
驅動的 action executor，以及大量測試組織、可觀測、安全與 AI 輔助工具。
所有 helper 都同時提供 Python API 與 ``WR_*`` action 命令。

每個註冊的 ``WR_*`` 命令（含 signature 與摘要）已自動產出於：

    docs/reference/command_reference.md

另有對應 action JSON 的 JSON Schema：

    docs/reference/webrunner-action-schema.json

架構
========

系統概觀
--------

.. mermaid::

   flowchart LR
     A1["Action JSON"] --> EXE["Executor"]
     A2["錄製器"] --> A1
     A3["LLM NL → 草稿"] --> A1
     EXE --> SEL["Selenium"]
     EXE --> PW["Playwright"]
     EXE --> APM["Appium"]
     EXE --> HTTP["HTTP API"]
     EXE --> DB["資料庫"]
     SEL --> REC["紀錄"]
     PW --> REC
     REC --> REP["報告"]
     REC --> OBS["可觀測"]
     REC --> NOT["通知"]

Action 生命週期
---------------

.. mermaid::

   flowchart LR
     IN["[cmd, args, kwargs]"] --> VAL["驗證器"]
     VAL --> ENV["${ENV.X} / ${ROW.x}"]
     ENV --> SPAN["OTel span"]
     SPAN --> RETRY["重試策略"]
     RETRY --> GATE["Script 開關"]
     GATE --> DISP["event_dict[cmd]"]
     DISP --> RECORD["records.append"]
     DISP -- 失敗 --> SHOT["自動截圖"]

Backends
========

Selenium（預設）
----------------

原本的 ``WebDriverWrapper`` 與 ``WebElementWrapper``。所有沒有特定前綴的
命令都會走這條。

Playwright
----------

完整鏡像 Selenium 的命令面，前綴為 ``WR_pw_*``：

* lifecycle / 分頁 / 導覽
* find（含 ``TestObject`` 自動翻譯）與直接的 page-level 快捷
* 元素層 wrapper
* 行動裝置模擬、locale、時區、地理位置、權限、clock
* HAR 錄製、route mock、console + 網路事件擷取
* 透過 CDP 的網路節流預設集

opt-in 設計：既有腳本可繼續跑在 Selenium 上。

雲端 Grid
---------

對應 BrowserStack / Sauce Labs / LambdaTest 的 helper。

Appium（行動）
--------------

``start_appium_session`` 建立 Appium driver 並掛在 Selenium wrapper 上，既
有 ``WR_*`` 命令直接適用 mobile session。

報告
====

五種格式 + 一份 manifest：

* HTML — 單一 ``<base>.html``
* JSON — 拆分 ``<base>_success.json`` + ``<base>_failure.json``
* XML — 拆分 ``<base>_success.xml`` + ``<base>_failure.xml``
* JUnit XML — 單一 ``<base>_junit.xml``（CI 原生）
* Allure — 目錄含多個 ``<uuid>-result.json``

``generate_all_reports(base, allure_dir=None)`` 一次跑完所有 generator 並
寫出 ``<base>.manifest.json`` 對應每個格式的實際路徑。

可觀測
======

* 失敗自動截圖
* 全域重試策略
* OpenTelemetry tracing hook（軟相依）
* 即時 progress dashboard（stdlib HTTP）
* Replay studio（HTML 時間軸）
* HAR 差異比對

測試組織
========

* 標籤過濾（``meta.tags``）
* 依賴宣告（``meta.depends_on``）+ 拓樸排序
* Run ledger + ``--rerun-failed``
* Flaky 測試偵測
* 拓樸 sharding（``--shard 1/4``）
* Multi-user matrix
* A/B run 模式
* Watch mode（``--watch``）
* 排程 runner

品質與安全
==========

* Action linter
* Migration helper（舊命令 → 新別名）
* 寫死密碼掃描
* HTTP 安全 headers 稽核
* axe-core 可訪問性
* Lighthouse 跑分
* Core Web Vitals
* Visual regression
* 文字 / DOM snapshot
* 網路節流預設集
* Arbitrary-script 開關

瀏覽器底層
==========

* 原生 CDP 直通
* localStorage / sessionStorage / IndexedDB
* Service Worker / cache
* Console + 網路事件擷取
* Shadow DOM piercing
* 多層 iframe
* 檔案上傳 / 下載
* 瀏覽器擴充功能載入

測試資料
========

* Faker 整合（軟相依）
* Factory 樣板
* Testcontainers（軟相依）
* ``.env`` 載入器 + ``${ENV.X}``
* 資料驅動 runner + ``${ROW.x}``

驗證
====

* OAuth2 / OIDC（含 token cache）
* HTTP API + 斷言
* 資料庫驗證（SQLAlchemy 軟相依，bound parameters only）

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

AI 輔助
=======

WebRunner 不打包任何 LLM client。透過 ``set_llm_callable(fn)`` 註冊任意
``Callable[[str], str]`` 即可：

* ``suggest_locator`` — 自我修復定位的 LLM 後援
* ``generate_actions_from_prompt`` — 自然語言生成 action 草稿
