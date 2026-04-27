====
報告
====

五種格式 + 一份 manifest：

* HTML — 單一 ``<base>.html``
* JSON — 拆分 ``<base>_success.json`` + ``<base>_failure.json``
* XML — 拆分 ``<base>_success.xml`` + ``<base>_failure.xml``
* JUnit XML — 單一 ``<base>_junit.xml``\ （CI 原生）
* Allure — 目錄含多個 ``<uuid>-result.json``

``generate_all_reports(base, allure_dir=None)`` 一次跑完所有 generator 並
寫出 ``<base>.manifest.json`` 對應每個格式的實際路徑。

報告 / CI 補強
==============

* ``pr_comment.post_or_update_comment`` — GitHub PR 自動留言（idempotent）
* ``trend_dashboard.compute_trend`` — ledger 日趨勢 + SVG 圖表

Lock file / a11y trend / perf drift
====================================

* ``workspace_lock.build_lock`` — pip 版本 + driver 版本 + Playwright
  browser 版本一起 pin，CI 完全 reproducible
* ``a11y_trend.aggregate_history`` + ``render_html`` — axe 違規數
  時間序列，自帶 SVG 圖表
* ``perf_drift.detect_drift`` — 滑動視窗 P95 比對，超 tolerance 即視為
  regression
