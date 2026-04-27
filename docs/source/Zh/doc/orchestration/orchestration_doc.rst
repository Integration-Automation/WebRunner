========
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

編排 / 開發者體驗
=================

* ``action_templates`` — login_basic / accept_cookies / switch_locale /
  close_modal 等可重用樣板
* ``sharding.diff_shard`` — 只跑 git diff 影響到的測試
* ``watch_mode.watch_loop`` — 檔案變動監看
* ``k8s_runner.render_job_manifests`` — 每個 shard 一個 batch/v1 Job
* ``perf_metrics.budgets`` — 每路由 FCP/LCP/CLS 預算

Fan-out / event bus / extension harness
=======================================

* ``fanout.run_fan_out`` — 同 test 內平行跑多個 callable，每個 task
  回報耗時與結果
* ``event_bus.EventBus`` — 檔案系統 ndjson pub/sub，跨 shard 協調用
* ``extension_harness`` — 解析 MV2/MV3 manifest，配置 Selenium 或
  Playwright 載入未打包擴充

CLI / 編排 polish
=================

* ``test_filter.name_filter.filter_paths`` — regex include/exclude 路徑
  篩選，與既有 tag filter 並行
* ``process_supervisor`` — 殺掉 orphan webdriver、給長 callable 上
  watchdog
* ``pipeline.load_pipeline`` + ``run_pipeline`` — 多階段 gate，
  ``continue_on_failure`` 可作為 lint / scan 收尾
