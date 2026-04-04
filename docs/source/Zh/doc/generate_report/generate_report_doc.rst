報告產生
========

概述
----

WebRunner 可以自動記錄所有動作，並產生三種格式的報告：
**HTML**、**JSON** 和 **XML**。報告包含每個執行動作的詳細資訊，
包括函式名稱、參數、時間戳記和例外資訊。

.. note::

   產生報告前必須先啟用測試記錄。

啟用記錄
--------

.. code-block:: python

    from je_web_runner import test_record_instance

    test_record_instance.set_record_enable(True)

HTML 報告
---------

HTML 報告包含顏色編碼的表格：

* **水藍色** 背景表示成功的動作
* **紅色** 背景表示失敗的動作

.. code-block:: python

    from je_web_runner import generate_html, generate_html_report

    # 產生 HTML 字串
    html_content = generate_html()

    # 儲存為檔案（建立 test_results.html）
    generate_html_report("test_results")

JSON 報告
---------

JSON 報告分別產生成功和失敗的檔案。

.. code-block:: python

    from je_web_runner import generate_json, generate_json_report

    # 產生字典（回傳 success_dict, failure_dict 元組）
    success_dict, failure_dict = generate_json()

    # 儲存為檔案：
    # - test_results_success.json
    # - test_results_failure.json
    generate_json_report("test_results")

XML 報告
---------

.. code-block:: python

    from je_web_runner import generate_xml, generate_xml_report

    # 產生 XML 結構
    success_xml, failure_xml = generate_xml()

    # 儲存為檔案：
    # - test_results_success.xml
    # - test_results_failure.xml
    generate_xml_report("test_results")

透過 Action Executor 產生報告
------------------------------

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        ["WR_set_record_enable", {"set_enable": True}],
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"],
        ["WR_generate_html_report", {"html_name": "my_report"}],
    ])

記錄資料格式
------------

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
