快速開始
========

本指南示範使用 WebRunner 的三種主要方式。

範例一：直接使用 Python API
-----------------------------

直接在 Python 程式碼中使用 WebRunner 的類別和函式。

.. code-block:: python

    from je_web_runner import TestObject
    from je_web_runner import get_webdriver_manager
    from je_web_runner import web_element_wrapper

    # 建立 WebDriver 管理器（使用 Chrome）
    manager = get_webdriver_manager("chrome")

    # 導航到網址
    manager.webdriver_wrapper.to_url("https://www.google.com")

    # 設定隱式等待
    manager.webdriver_wrapper.implicitly_wait(2)

    # 建立測試物件來定位搜尋框
    search_box = TestObject("q", "name")

    # 尋找元素
    manager.webdriver_wrapper.find_element(search_box)

    # 點擊並輸入文字
    web_element_wrapper.click_element()
    web_element_wrapper.input_to_element("WebRunner automation")

    # 關閉瀏覽器
    manager.quit()

範例二：JSON 動作列表
----------------------

將自動化腳本定義為 JSON 動作列表，透過 Action Executor 執行。

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://www.google.com"}],
        ["WR_implicitly_wait", {"time_to_wait": 2}],
        ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
        ["WR_find_element", {"element_name": "q"}],
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "WebRunner automation"}],
        ["WR_quit"]
    ]

    result = execute_action(actions)

範例三：從 JSON 檔案執行
--------------------------

建立 ``actions.json`` 檔案：

.. code-block:: json

    [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]

在 Python 中執行：

.. code-block:: python

    from je_web_runner import execute_files

    results = execute_files(["actions.json"])

或使用命令列：

.. code-block:: bash

    python -m je_web_runner -e actions.json

範例四：無頭模式
-----------------

使用無頭模式在沒有可見 GUI 視窗的情況下執行瀏覽器。

.. code-block:: python

    from je_web_runner import get_webdriver_manager

    manager = get_webdriver_manager("chrome", options=["--headless", "--disable-gpu"])
    manager.webdriver_wrapper.to_url("https://example.com")
    title = manager.webdriver_wrapper.execute_script("return document.title")
    print(f"頁面標題: {title}")
    manager.quit()
