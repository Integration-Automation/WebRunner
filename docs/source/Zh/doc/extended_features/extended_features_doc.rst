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

詳細功能文件已拆分成下列子主題頁，並在主目錄中歸入對應章節；
此處僅以隱藏 toctree 保留交互參照，方便舊版指南仍能透過
``extended_features`` 連到內頁。

.. toctree::
   :hidden:

   ../architecture/architecture_doc.rst
   ../backends/backends_doc.rst
   ../reports/reports_doc.rst
   ../observability/observability_doc.rst
   ../orchestration/orchestration_doc.rst
   ../quality_security/quality_security_doc.rst
   ../browser_internals/browser_internals_doc.rst
   ../data_auth_api/data_auth_api_doc.rst
   ../integrations/integrations_doc.rst
   ../tooling/tooling_doc.rst
   ../cookbook/cookbook_doc.rst
