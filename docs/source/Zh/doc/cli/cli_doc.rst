命令列介面
==========

概述
----

WebRunner 可以直接從命令列使用 ``je_web_runner`` 模組執行。

指令
----

**執行單一 JSON 動作檔案：**

.. code-block:: bash

    python -m je_web_runner -e actions.json
    python -m je_web_runner --execute_file actions.json

**執行目錄中所有 JSON 檔案：**

.. code-block:: bash

    python -m je_web_runner -d ./actions/
    python -m je_web_runner --execute_dir ./actions/

**直接執行 JSON 動作字串：**

.. code-block:: bash

    python -m je_web_runner --execute_str '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_quit"]]'

指令參考
--------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - 旗標
     - 簡寫
     - 說明
   * - ``--execute_file``
     - ``-e``
     - 執行單一 JSON 動作檔案
   * - ``--execute_dir``
     - ``-d``
     - 執行目錄中所有 JSON 檔案
   * - ``--execute_str``
     -
     - 直接執行 JSON 動作字串

.. note::

   在 Windows 上，``--execute_str`` 選項可能需要雙重 JSON 解析（因 shell 跳脫字元）。
   WebRunner 會自動處理此情況。

錯誤處理
--------

若未提供任何參數，WebRunner 會引發 ``WebRunnerExecuteException``。
所有錯誤會輸出到 stderr，程序以代碼 1 退出。
