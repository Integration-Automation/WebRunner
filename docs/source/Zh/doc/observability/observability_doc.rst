======
可觀測
======

* 失敗自動截圖
* 全域重試策略
* OpenTelemetry tracing hook（軟相依）
* 即時 progress dashboard（stdlib HTTP）：``start_dashboard("127.0.0.1", 8080)``
  即時顯示目前這次執行的進度
* 彙整儀表板：``DashboardServer(DashboardConfig(...)).start()``
  （``utils/live_dashboard``）顯示其他模組寫出的檔案裡的歷史資料：
  ``ledger_path``（執行紀錄、每日通過率圖表、flake 分數）、``quarantine_path``、
  ``locator_findings_path``、``schedule_path``（``test_scheduler``）與
  ``triage_report_path``（``failure_triage``）。頁面有 Overview、Runs、Flake、
  Quarantine、Locators、Schedule、Triage；設為 ``None`` 的來源會顯示空狀態並
  說明該設定哪個欄位。表格可排序、篩選，時間以瀏覽器時區顯示，資料每 15 秒
  更新（可按 Pause 暫停），淺色與深色跟隨系統。同樣的資料以 JSON 提供於
  ``/api/summary``、``/api/runs``、``/api/flake``、``/api/quarantine``、
  ``/api/locators``、``/api/schedule``、``/api/triage``、``/api/trend``。只用
  標準函式庫，預設綁定 127.0.0.1；頁面不靠 JavaScript 也能用，並在
  ``Content-Security-Policy: default-src 'self'`` 下提供，所有值都經過 HTML 跳脫
* Replay studio（HTML 時間軸）
* HAR 差異比對

可觀測性工具
============

* ``observability.timeline.build`` — 合併 OTel span / console / 網路回應
* ``failure_bundle.FailureBundle`` — 失敗素材打包成可重現的 zip
* ``memory_leak.detect_growth`` — heap 線性回歸找洩漏
* ``trace_recorder.TraceRecorder`` — Playwright tracing 包裝
* ``csp_reporter.CspViolationCollector`` — CSP 違規監聽

Triage / 線上 Observability
===========================

* ``failure_cluster.cluster_failures`` — 把失敗依 normalised signature
  分群、列出 top buckets
* ``synthetic_monitoring.SyntheticMonitor`` — 固定 subset 對 prod 持續
  輪播，狀態 edge-triggered alert
* ``observability.otlp_exporter`` — 把現有 OTel spans 寄到 OTLP gRPC /
  HTTP 後端（Jaeger / Tempo）
