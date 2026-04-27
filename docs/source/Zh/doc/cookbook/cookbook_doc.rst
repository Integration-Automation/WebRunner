==========================================
範例、測試分層、主題式 façade
==========================================

Cookbook 範例
=============

``examples/`` 提供可直接跑的真實 Chrome 範例，每個都剛好揪出一個既有 bug：

* ``counting_stars.{py,json}`` — 開 YouTube 播 OneRepublic Counting Stars
  （順帶揪出 ``execute_script`` 吞回傳值的 bug）
* ``google_search.py`` — 處理 GDPR 同意彈窗、抓首個搜尋結果標題
* ``form_submit.py`` — ``form_autofill`` + ``state_diff`` 串連 httpbin
* ``smart_wait_demo.py`` — fetch idle / SPA route stable / memory leak
* ``fanout_demo.py`` — ``run_fan_out`` 平行 HTTP preflight
* ``pii_redact_demo.py`` — 純邏輯 PII redaction

測試分層
========

* ``test/unit_test/`` — 1200 個 mock-based 單元測試，約 12 秒
* ``test/integration_test/`` — 30 個整合測試，串接真 I/O（SQLite、HTTP
  server、MCP / LSP 子行程），曾揪出 Windows LSP CRLF framing bug
* ``test/e2e_test/`` — 六個真瀏覽器 smoke，``WEBRUNNER_E2E_HUB`` 未設定
  時自動 skip。本機跑：``cd docker && docker compose up -d``。CI 走
  ``.github/workflows/e2e_browser.yml``，每日 + 手動觸發

主題式 façade
=============

80+ helpers 除了原本的 ``je_web_runner.utils.<area>`` 路徑，現在也透過
``je_web_runner.api`` 主題分組重新匯出：

.. code-block:: python

   from je_web_runner.api import (
       authoring, debugging, frontend, infra, mobile,
       networking, observability, quality, reliability,
       security, test_data,
   )

原本的 Selenium 式頂層 API 不變，舊程式碼可繼續運作。
