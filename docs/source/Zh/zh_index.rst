====================================
WebRunner 繁體中文文件
====================================

中文手冊依「安裝 → 操作瀏覽器 → 撰寫動作 → 擴展 → 整合」的順序拆成多個章節，
請從左側目錄選擇章節，或從下方直接跳轉。

.. contents:: 本頁目錄
   :local:
   :depth: 1

----

.. _zh-getting-started:

第 1 章 — 入門
==============

安裝 WebRunner、跑第一支瀏覽器腳本、以及產生新專案骨架。

.. toctree::
    :maxdepth: 2
    :caption: 入門

    doc/installation/installation_doc.rst
    doc/quick_start/quick_start_doc.rst
    doc/create_project/create_project_doc.rst

.. _zh-core-wrappers:

第 2 章 — 核心包裝器
====================

對 Selenium 的封裝層：driver、options、element 與 locator 值物件，
讀完這章後其他模組會變得直觀。

.. toctree::
    :maxdepth: 2
    :caption: 核心包裝器

    doc/architecture/architecture_doc.rst
    doc/webdriver_wrapper/webdriver_wrapper_doc.rst
    doc/webdriver_manager/webdriver_manager_doc.rst
    doc/webdriver_options/webdriver_options_doc.rst
    doc/web_element/web_element_doc.rst
    doc/test_object/test_object_doc.rst

.. _zh-actions:

第 3 章 — 動作撰寫與執行
========================

撰寫 JSON 驅動的 action 腳本、註冊 callback、外掛動態載入、
以及記錄瀏覽器執行軌跡。

.. toctree::
    :maxdepth: 2
    :caption: 動作

    doc/action_executor/action_executor_doc.rst
    doc/assertion/assertion_doc.rst
    doc/callback_function/callback_function_doc.rst
    doc/test_record/test_record_doc.rst
    doc/package_manager/package_manager_doc.rst

.. _zh-backends:

第 4 章 — 瀏覽器後端
====================

Selenium 與 Playwright 後端,以及更底層的瀏覽器整合(CDP、capability、
網路條件)。

.. toctree::
    :maxdepth: 2
    :caption: 瀏覽器後端

    doc/backends/backends_doc.rst
    doc/browser_internals/browser_internals_doc.rst

.. _zh-reporting:

第 5 章 — 報告與觀測性
======================

產生 HTML / JSON / XML 報告、輸出 log、暴露 metrics、以及跨 run 的趨勢比對。

.. toctree::
    :maxdepth: 2
    :caption: 報告

    doc/generate_report/generate_report_doc.rst
    doc/reports/reports_doc.rst
    doc/observability/observability_doc.rst
    doc/logging/logging_doc.rst

.. _zh-orchestration:

第 6 章 — 調度與擴展
====================

平行執行、shard 拆分、重試、Selenium Grid、以及 Kubernetes Job 範本。

.. toctree::
    :maxdepth: 2
    :caption: 調度

    doc/orchestration/orchestration_doc.rst

.. _zh-quality:

第 7 章 — 品質、安全與資料
==========================

Action linter、locator 評分、PII 偵測與遮罩、accessibility diff、
contract testing、資料/認證 helper。

.. toctree::
    :maxdepth: 2
    :caption: 品質與資料

    doc/quality_security/quality_security_doc.rst
    doc/data_auth_api/data_auth_api_doc.rst

.. _zh-tooling:

第 8 章 — 工具、CLI 與診斷
==========================

命令列介面、遠端 socket driver、以及在 traceback 中會看到的例外階層。

.. toctree::
    :maxdepth: 2
    :caption: 工具

    doc/cli/cli_doc.rst
    doc/tooling/tooling_doc.rst
    doc/socket_driver/socket_driver_doc.rst
    doc/exception/exception_doc.rst

.. _zh-integrations:

第 9 章 — 外部整合
==================

CI 註解、JIRA / TestRail / Slack 通知、IDE schema 設定,以及讓 Claude 透過
**Model Context Protocol (MCP)** 操作 WebRunner 的 server。

.. toctree::
    :maxdepth: 2
    :caption: 整合

    doc/integrations/integrations_doc.rst
    doc/mcp_claude/mcp_claude_doc.rst
    doc/cookbook/cookbook_doc.rst

.. _zh-reference:

第 10 章 — 參考資料
===================

舊的 extended features hub 頁面,留作向下相容,實際內容已分散到上面各章。

.. toctree::
    :maxdepth: 2
    :caption: 參考

    doc/extended_features/extended_features_doc.rst
