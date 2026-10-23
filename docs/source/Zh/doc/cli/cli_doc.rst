命令列介面
==========

概述
----

WebRunner 可以直接從命令列使用 ``je_web_runner`` 模組執行。安裝套件時也會裝上
主控台指令 ``webrunner`` 與 ``web_runner``，旗標、輸出與結束碼都相同，所以
``webrunner -e actions.json`` 等於 ``python -m je_web_runner -e actions.json``
（也可以用 ``pipx run --spec je_web_runner webrunner``）。

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

失敗的動作不會中止所在的清單：其餘動作會繼續執行，``-d`` 的其餘檔案也是。全部執行完之後，
只要有任何失敗，程序就以代碼 1 退出並印出 ``error: N action(s) or file(s) failed``，否則以 0 退出。

在 TestPioneer 之下執行
-----------------------

TestPioneer 啟動 runner 時會把 ``TEST_PIONEER_ARTIFACT_DIR`` 設為該次執行的輸出目錄。
以相對名稱要求的報告（JSON、XML、HTML、JUnit、Allure、互動式 HTML，以及 ``generate_all_reports``）
會寫到該目錄底下，所需的資料夾會自動建立。絕對路徑，以及會離開該目錄的名稱，則照原樣使用。
沒有設定這個變數時，行為不變。

本機 Agent 任務
---------------

``--agent-task task.json --report results/task`` 執行可驗證的本機任務。
詳見 :doc:`../integrations/local_agent_doc`。
