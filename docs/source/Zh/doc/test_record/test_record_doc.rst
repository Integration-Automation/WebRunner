測試記錄
========

概述
----

所有 WebRunner 動作都可以自動記錄，用於稽核追蹤和報告產生。
全域實例 ``test_record_instance`` 管理記錄狀態和儲存記錄。

啟用記錄
--------

記錄預設為停用。在執行動作前啟用：

.. code-block:: python

    from je_web_runner import test_record_instance

    test_record_instance.set_record_enable(True)

或透過動作執行器：

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        ["WR_set_record_enable", {"set_enable": True}],
    ])

存取記錄
--------

.. code-block:: python

    records = test_record_instance.test_record_list

    for record in records:
        print(record)

記錄格式
--------

每筆記錄是一個字典，包含以下欄位：

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - 欄位
     - 型別
     - 說明
   * - ``function_name``
     - ``str``
     - 執行的函式名稱
   * - ``local_param``
     - ``dict | None``
     - 傳遞給函式的參數
   * - ``time``
     - ``str``
     - 執行時間戳記
   * - ``program_exception``
     - ``str``
     - 例外訊息或 ``"None"``

清除記錄
--------

.. code-block:: python

    test_record_instance.clean_record()
