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
* ``explain_failure`` — 從失敗素材生成 RCA：``{likely_cause, evidence,
  next_steps, confidence}``

可靠度
======

* ``adaptive_retry.run_with_retry`` — 依 classifier 結果決定是否重試
* ``linter.locator_strength.score_locator`` — locator 0–100 分強度評估
* ``smart_wait.wait_for_fetch_idle`` / ``wait_for_spa_route_stable`` —
  比 ``time.sleep`` 智慧的 SPA 等待
* ``throttler.throttle("svc")`` — 跨 shard 的檔案信號量

可觀測性
========

* ``observability.timeline.build`` — 合併 OTel span / console / 網路回應
* ``failure_bundle.FailureBundle`` — 失敗素材打包成可重現的 zip
* ``memory_leak.detect_growth`` — heap 線性回歸找洩漏
* ``trace_recorder.TraceRecorder`` — Playwright tracing 包裝
* ``csp_reporter.CspViolationCollector`` — CSP 違規監聽

測試資料 / 確定性
=================

* ``snapshot.fixture_record.FixtureRecorder`` — 第一次跑記錄、之後重放
* ``database.fixtures`` — YAML/JSON → SQLAlchemy 連線 seed

API 與合約
==========

* ``api_mock.MockRouter`` — Playwright route() 上層的宣告式 mock
* ``contract_testing`` — JSON Schema 子集 + OpenAPI ``$ref`` 解析
* ``graphql.GraphQLClient`` — GraphQL HTTP client + ``extract_field``
* ``mock_services`` — SMTP / OAuth / S3 in-process mock

安全測試
========

* ``header_tampering.HeaderTampering`` — 改 cookie/referer/origin
* ``license_scanner`` — SPDX / 已知授權字樣偵測
* ``cookie_consent.ConsentDismisser`` — 自動關閉 GDPR 彈窗

裝置 / 區域
===========

* ``device_emulation`` — iPhone / Pixel / iPad / Desktop 預設
* ``geo_locale`` — geolocation / timezone / locale 一次設定
* ``multi_tab.TabChoreographer`` — 多分頁腳本連動
* ``webauthn.enable_virtual_authenticator`` — passkey / FIDO2 模擬

報告 / CI
=========

* ``pr_comment.post_or_update_comment`` — GitHub PR 自動留言（idempotent）
* ``trend_dashboard.compute_trend`` — ledger 日趨勢 + SVG 圖表

編排 / 開發者體驗
=================

* ``action_templates`` — login_basic / accept_cookies / switch_locale /
  close_modal 等可重用樣板
* ``sharding.diff_shard`` — 只跑 git diff 影響到的測試
* ``watch_mode.watch_loop`` — 檔案變動監看
* ``k8s_runner.render_job_manifests`` — 每個 shard 一個 batch/v1 Job
* ``perf_metrics.budgets`` — 每路由 FCP/LCP/CLS 預算

MCP server
==========

提供 Model Context Protocol stdio JSON-RPC server：

.. code-block:: shell

   python -m je_web_runner.mcp_server

預設工具：``webrunner_lint_action`` / ``webrunner_locator_strength`` /
``webrunner_render_template`` / ``webrunner_compute_trend`` /
``webrunner_validate_response`` / ``webrunner_summary_markdown`` /
``webrunner_diff_shard`` / ``webrunner_render_k8s`` /
``webrunner_partition_shard``。可透過 ``McpServer.register(Tool(...))``
擴充自訂工具，協定版本 ``2024-11-05``。
