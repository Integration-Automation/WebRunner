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

互動式 HTML 報告
----------------

``generate_interactive_html_report(html_name, screenshot_dir=None,
har_path=None, a11y_results=None)``\ （``WR_generate_interactive_html_report``）
寫出一個自給自足的 ``<html_name>.html``，沒有外部資源也沒有 script，每一段
都以 ``<details>`` 展開：

* 每個紀錄步驟的時間軸，失敗的預設展開，``screenshot_dir`` 的截圖內嵌在它
  之後的步驟下（失敗截圖以時間命名，其他圖片依修改時間）；
* 每個失敗的完整錯誤，斷言比較兩個值時（``a != b``、``expected X but got Y``）
  再附上 unified diff；
* 由 HAR 1.2 檔案畫出的網路瀑布圖；
* axe-core 違規依嚴重度的徽章，來源可以是結果 dict 或它的 JSON 檔。

.. code-block:: python

    from je_web_runner import generate_interactive_html_report

    generate_interactive_html_report("run", screenshot_dir="failures",
                                     har_path="run.har", a11y_results="axe.json")

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
