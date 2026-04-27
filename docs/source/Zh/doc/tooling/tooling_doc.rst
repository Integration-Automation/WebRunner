====
工具
====

可靠度
======

* ``adaptive_retry.run_with_retry`` — 依 classifier 結果決定是否重試
* ``linter.locator_strength.score_locator`` — locator 0–100 分強度評估
* ``smart_wait.wait_for_fetch_idle`` / ``wait_for_spa_route_stable`` —
  比 ``time.sleep`` 智慧的 SPA 等待
* ``throttler.throttle("svc")`` — 跨 shard 的檔案信號量

Browser pool / BiDi bridge
==========================

* ``browser_pool.BrowserPool`` — 暖機 N 個 browser instance、checkout/
  checkin、健康檢查與最大次數淘汰
* ``bidi_backend.BidiBridge`` — 跨 Selenium 4 BiDi 與 Playwright 的
  事件訂閱統一介面，可 ``register_translator`` 擴充

HAR replay server
=================

把 ``har_replay.load_har("recorded.har")`` 載入後給
``HarReplayServer(entries).start()`` 啟用本機 HTTP server，URL pattern
支援字面 / glob / ``re:`` regex、重複條目自動輪播。

Test impact analysis
====================

``impact_analysis.build_index("./actions")`` 走訪 action JSON 建立
locator / URL / template / command 反查表；
``affected_action_files(index, locators=["primary_cta"])`` 回傳所有
參考此 locator 的測試檔，搭配 ``sharding.diff_shard`` 做精準測試選擇。

Bootstrapper / driver pinner
============================

* ``bootstrapper.init_workspace`` — 一鍵 scaffold 起手式
  （sample actions / ledger / pre-commit / GitHub Actions）
* ``driver_pin.install_for_browser`` — 讀 ``.webrunner/drivers.json``
  下載並快取 driver，避開 webdriver-manager 的 GitHub API 限流

Selenium → Playwright 翻譯
==========================

* ``sel_to_pw.translate_python_source`` — 常見 Selenium 寫法靜態翻譯成
  Playwright 等價（``find_element(By.ID, "x")`` → ``page.locator("#x")``）
* ``sel_to_pw.translate_action_list`` — ``WR_*`` action JSON 轉
  ``WR_pw_*``、自動丟掉 ``WR_implicitly_wait``

Action formatter / Markdown 撰寫
================================

* ``action_formatter.format_actions`` — canonical 縮排與鍵順序，搭配
  既有 LSP 一起用
* ``md_authoring.parse_markdown`` — 用 Markdown bullet 寫測試流程，再
  轉成 ``WR_*`` action JSON

Page Object codegen
===================

``pom_codegen.discover_elements_from_html`` 走過 HTML 抓
``data-testid`` / ``id`` / form fields，``render_pom_module`` 產生
Python POM 模組。

Coverage map
============

* ``coverage_map.build_coverage_map`` — 從 action JSON 抽出 ``WR_to_url``
  的 path 建立 route → files 反查表，``coverage.uncovered`` 找出未覆蓋
  的 route

WR_sleep
========

Executor 內建的同步 sleep 命令，給 action JSON 用：

.. code-block:: json

   [
     ["WR_to_url", {"url": "https://example.com"}],
     ["WR_sleep", {"seconds": 2.5}],
     ["WR_get_screenshot_as_png"]
   ]

負數 / 非數字會丟 ``ValueError``，typo 不會被默默忽略。
