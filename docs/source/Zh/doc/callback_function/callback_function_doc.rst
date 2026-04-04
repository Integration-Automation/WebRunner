回調執行器
==========

概述
----

回調執行器允許您執行自動化指令，並在完成後觸發回調函式。
它包裝了標準執行器的事件字典，提供事件驅動的執行模型。

全域實例 ``callback_executor`` 從 ``je_web_runner`` 匯入。

基本用法
--------

.. code-block:: python

    from je_web_runner import callback_executor

    def on_complete():
        print("導航完成！")

    callback_executor.callback_function(
        trigger_function_name="WR_to_url",
        callback_function=on_complete,
        url="https://example.com"
    )

使用 kwargs 的回調
-------------------

.. code-block:: python

    def on_element_found(result=None):
        print(f"找到元素: {result}")

    callback_executor.callback_function(
        trigger_function_name="WR_find_element",
        callback_function=on_element_found,
        callback_function_param={"result": "search_box"},
        callback_param_method="kwargs",
        element_name="search_box"
    )

使用 args 的回調
-----------------

.. code-block:: python

    def on_done(msg):
        print(f"完成: {msg}")

    callback_executor.callback_function(
        trigger_function_name="WR_quit",
        callback_function=on_done,
        callback_function_param=["所有瀏覽器已關閉"],
        callback_param_method="args"
    )

參數
----

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - 參數
     - 型別
     - 說明
   * - ``trigger_function_name``
     - ``str``
     - 要觸發的函式名稱（必須存在於 ``event_dict``）
   * - ``callback_function``
     - ``Callable``
     - 觸發後要執行的回調函式
   * - ``callback_function_param``
     - ``dict | list | None``
     - 傳遞給回調的參數
   * - ``callback_param_method``
     - ``str``
     - 回調參數傳遞方式：``"kwargs"`` 或 ``"args"``
   * - ``**kwargs``
     -
     - 傳遞給觸發函式的參數
