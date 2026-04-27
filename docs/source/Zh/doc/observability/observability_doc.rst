======
可觀測
======

* 失敗自動截圖
* 全域重試策略
* OpenTelemetry tracing hook（軟相依）
* 即時 progress dashboard（stdlib HTTP）
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
