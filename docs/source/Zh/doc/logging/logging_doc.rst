日誌
====

概述
----

WebRunner 使用 Python 的 ``logging`` 模組搭配旋轉檔案處理器來記錄自動化事件、錯誤和警告。

設定
----

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 屬性
     - 值
   * - 日誌檔案
     - ``WEBRunner.log``
   * - 日誌等級
     - ``WARNING`` 及以上
   * - 最大檔案大小
     - 1 GB（旋轉）
   * - 日誌格式
     - ``%(asctime)s | %(name)s | %(levelname)s | %(message)s``
   * - 處理器
     - ``RotatingFileHandler``（自訂 ``WebRunnerLoggingHandler``）

日誌輸出
--------

日誌檔案在當前工作目錄中建立為 ``WEBRunner.log``。
當檔案達到 1 GB 時會進行旋轉。

日誌範例：

.. code-block:: text

    2025-01-01 12:00:00 | je_web_runner | WARNING | WebDriverWrapper find_element failed: ...
    2025-01-01 12:00:01 | je_web_runner | ERROR | WebdriverManager quit, failed: ...

日誌實例
--------

全域日誌可透過 ``web_runner_logger`` 存取：

.. code-block:: python

    from je_web_runner.utils.logging.loggin_instance import web_runner_logger

    web_runner_logger.warning("自訂警告訊息")
