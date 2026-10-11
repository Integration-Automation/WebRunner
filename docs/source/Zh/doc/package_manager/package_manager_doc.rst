套件管理器
==========

概述
----

套件管理器可在執行期間動態載入外部 Python 套件到執行器中。
當套件被加入後，其所有公開函式和類別會以 ``{套件名}_{函式名}`` 的命名慣例註冊到事件字典。

透過 Action Executor 使用
--------------------------

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        # 將 'time' 套件載入執行器
        ["WR_add_package_to_executor", {"package": "time"}],

        # 現在可以使用 time.sleep（名稱為 "time_sleep"）
        ["time_sleep", [2]],
    ]

    execute_action(actions)

套件閘門
--------

載入套件會把它的函式註冊成命令，所以能寫出 ``os`` 或 ``subprocess`` 的
action 檔就能執行任何東西。由主程式決定 action 檔可以載入哪些套件：

.. code-block:: python

    from je_web_runner.utils.executor.action_executor import executor

    executor.allow_packages("my_helpers")          # 這些套件與其子模組
    executor.set_allow_arbitrary_packages(False)   # 拒絕其他所有套件

被拒絕的套件在匯入前就丟出 ``WebRunnerExecuteException``，並記在該動作的
結果裡。``set_allow_arbitrary_packages(True)`` 則載入任何套件、不發警告。
兩個開關都不是 action 命令，所以 action 檔無法自行打開閘門。

預設就是拒絕：主程式把套件列入清單，或呼叫 ``set_allow_arbitrary_packages(True)``
以前，``WR_add_package_to_executor`` 都會拒絕它。

直接 API 使用
--------------

.. code-block:: python

    from je_web_runner.utils.package_manager.package_manager_class import package_manager

    # 檢查套件是否存在並匯入
    module = package_manager.check_package("os")

    # 將套件的所有函式加入執行器
    package_manager.add_package_to_executor("math")

    # 加入回調執行器
    package_manager.add_package_to_callback_executor("time")

方法
----

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - 方法
     - 參數
     - 說明
   * - ``check_package()``
     - ``package: str``
     - 檢查並匯入套件，回傳模組或 None
   * - ``add_package_to_executor()``
     - ``package: str``
     - 將套件成員加入 Executor 的 event_dict
   * - ``add_package_to_callback_executor()``
     - ``package: str``
     - 將套件成員加入 CallbackExecutor 的 event_dict
