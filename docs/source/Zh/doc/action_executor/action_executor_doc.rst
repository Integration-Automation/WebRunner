動作執行器
==========

概述
----

動作執行器是一個強大的引擎，將指令字串對應到可呼叫的函式。
它允許您將自動化腳本定義為 JSON 動作列表，實現資料驅動的自動化工作流程。

執行器還包含所有 Python 內建函式，因此可以在動作列表中呼叫 ``print``、``len`` 等。

動作格式
--------

每個動作是一個包含指令名稱和可選參數的列表：

.. code-block:: python

    ["command_name"]                        # 無參數
    ["command_name", {"key": "value"}]      # 關鍵字參數
    ["command_name", [arg1, arg2]]          # 位置參數

基本用法
--------

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://www.google.com"}],
        ["WR_implicitly_wait", {"time_to_wait": 2}],
        ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
        ["WR_find_element", {"element_name": "q"}],
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "WebRunner"}],
        ["WR_quit"]
    ]

    result = execute_action(actions)

``execute_action()`` 回傳一個字典，將每個動作對應到其回傳值。

可用指令
--------

完整的指令列表請參閱英文文件的 Action Executor 頁面。

主要指令分類：

* **WebDriver 管理**：``WR_get_webdriver_manager``, ``WR_change_index_of_webdriver``, ``WR_quit``
* **導航**：``WR_to_url``, ``WR_forward``, ``WR_back``, ``WR_refresh``
* **元素尋找**：``WR_find_element``, ``WR_find_elements``
* **等待**：``WR_implicitly_wait``, ``WR_explict_wait``, ``WR_set_script_timeout``, ``WR_set_page_load_timeout``
* **滑鼠**：``WR_left_click``, ``WR_right_click``, ``WR_left_double_click``, ``WR_drag_and_drop``
* **鍵盤**：``WR_press_key``, ``WR_release_key``, ``WR_send_keys``, ``WR_send_keys_to_element``
* **Cookie**：``WR_get_cookies``, ``WR_add_cookie``, ``WR_delete_cookie``, ``WR_delete_all_cookies``
* **JavaScript**：``WR_execute``, ``WR_execute_script``, ``WR_execute_async_script``
* **視窗**：``WR_maximize_window``, ``WR_minimize_window``, ``WR_set_window_size``
* **截圖**：``WR_get_screenshot_as_png``, ``WR_get_screenshot_as_base64``
* **元素操作**：``WR_click_element``, ``WR_input_to_element``, ``WR_element_clear``, ``WR_element_submit``
* **測試物件**：``WR_SaveTestObject``, ``WR_CleanTestObject``
* **報告**：``WR_generate_html_report``, ``WR_generate_json_report``, ``WR_generate_xml_report``
* **套件**：``WR_add_package_to_executor``, ``WR_add_package_to_callback_executor``

從 JSON 檔案執行
-----------------

.. code-block:: python

    from je_web_runner import execute_files

    results = execute_files(["actions1.json", "actions2.json"])

新增自訂指令
------------

.. code-block:: python

    from je_web_runner import add_command_to_executor

    def my_custom_function(param1, param2):
        print(f"自訂: {param1}, {param2}")

    add_command_to_executor({"my_command": my_custom_function})

    # 在動作列表中使用
    execute_action([
        ["my_command", {"param1": "hello", "param2": "world"}]
    ])

.. note::

   僅接受 ``types.MethodType`` 和 ``types.FunctionType``。
   傳入其他可呼叫類型會引發 ``WebRunnerAddCommandException``。
