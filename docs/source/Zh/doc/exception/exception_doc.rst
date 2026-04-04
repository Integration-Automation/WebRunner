例外處理
========

概述
----

WebRunner 提供自訂例外階層結構。所有例外繼承自 ``WebRunnerException``。

例外階層
--------

.. code-block:: text

    WebRunnerException（基底）
    ├── WebRunnerWebDriverNotFoundException
    ├── WebRunnerOptionsWrongTypeException
    ├── WebRunnerArgumentWrongTypeException
    ├── WebRunnerWebDriverIsNoneException
    ├── WebRunnerExecuteException
    ├── WebRunnerAssertException
    ├── WebRunnerHTMLException
    ├── WebRunnerAddCommandException
    ├── WebRunnerJsonException
    │   └── WebRunnerGenerateJsonReportException
    ├── XMLException
    │   └── XMLTypeException
    └── CallbackExecutorException

例外參考
--------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 例外
     - 說明
   * - ``WebRunnerException``
     - 所有 WebRunner 錯誤的基底例外
   * - ``WebRunnerWebDriverNotFoundException``
     - 找不到 WebDriver 或不支援的瀏覽器名稱
   * - ``WebRunnerOptionsWrongTypeException``
     - 提供了無效的選項型別
   * - ``WebRunnerArgumentWrongTypeException``
     - 提供了無效的參數型別
   * - ``WebRunnerWebDriverIsNoneException``
     - WebDriver 為 None（未初始化）
   * - ``WebRunnerExecuteException``
     - 動作執行錯誤（未知指令、無效格式）
   * - ``WebRunnerJsonException``
     - JSON 處理錯誤
   * - ``WebRunnerGenerateJsonReportException``
     - JSON 報告產生錯誤
   * - ``WebRunnerAssertException``
     - 斷言驗證失敗
   * - ``WebRunnerHTMLException``
     - HTML 報告產生錯誤
   * - ``WebRunnerAddCommandException``
     - 註冊自訂指令錯誤（非函式／方法）
   * - ``XMLException``
     - XML 處理錯誤
   * - ``XMLTypeException``
     - 無效的 XML 類型
   * - ``CallbackExecutorException``
     - 回調執行錯誤

範例
----

.. code-block:: python

    from je_web_runner import get_webdriver_manager
    from je_web_runner.utils.exception.exceptions import (
        WebRunnerException,
        WebRunnerWebDriverNotFoundException,
    )

    try:
        manager = get_webdriver_manager("unsupported_browser")
    except WebRunnerWebDriverNotFoundException as e:
        print(f"不支援的瀏覽器: {e}")
    except WebRunnerException as e:
        print(f"WebRunner 錯誤: {e}")
