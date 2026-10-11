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
     - ``$WEBRUNNER_LOG_PATH``\ （完整檔案路徑），否則
       ``$WEBRUNNER_LOG_DIR/WEBRunner.log``，都沒設就是
       ``~/.je_web_runner/logs/WEBRunner.log``
   * - 日誌等級
     - ``WARNING`` 及以上
   * - 輪替
     - 行程開檔時若超過 10 MB，先改名成 ``<name>.1``
   * - 日誌格式
     - ``%(asctime)s | %(process)d | %(name)s | %(levelname)s | %(message)s``
   * - 處理器
     - ``RotatingFileHandler``（自訂 ``WebRunnerLoggingHandler``）

日誌輸出
--------

import ``je_web_runner`` 不寫任何檔案：第一筆紀錄才建立檔案與目錄，並以附加模式
寫入，同一個帳號的行程可以共用。相對路徑以 import 當下的工作目錄為準；
``os.devnull`` 會關掉檔案輸出。開不了的檔案會改寫到 ``os.devnull`` 並發出一次
``RuntimeWarning``。

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
