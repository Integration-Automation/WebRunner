Web 元素包裝器
===============

概述
----

``WebElementWrapper`` 提供與已定位元素互動的方法。
它操作由 ``find_element()`` 或 ``find_elements()`` 設定的當前活動元素。

全域實例 ``web_element_wrapper`` 從 ``je_web_runner`` 匯入。

基本互動
--------

.. code-block:: python

    from je_web_runner import web_element_wrapper

    web_element_wrapper.click_element()                     # 點擊元素
    web_element_wrapper.input_to_element("Hello World")     # 輸入文字
    web_element_wrapper.clear()                             # 清除內容
    web_element_wrapper.submit()                            # 提交表單

屬性檢查
--------

.. code-block:: python

    web_element_wrapper.get_attribute("href")        # 取得 HTML 屬性
    web_element_wrapper.get_property("checked")      # 取得 JS 屬性
    web_element_wrapper.get_dom_attribute("data-id")  # 取得 DOM 屬性

狀態檢查
--------

.. code-block:: python

    web_element_wrapper.is_displayed()    # 檢查是否可見
    web_element_wrapper.is_enabled()      # 檢查是否可用
    web_element_wrapper.is_selected()     # 檢查是否被選取（核取方塊／單選）

CSS 屬性
---------

.. code-block:: python

    web_element_wrapper.value_of_css_property("color")

下拉選單處理
------------

.. code-block:: python

    select = web_element_wrapper.get_select()
    # 使用 Selenium 的 Select API：
    # select.select_by_visible_text("選項一")
    # select.select_by_value("opt1")
    # select.select_by_index(0)

元素截圖
--------

.. code-block:: python

    web_element_wrapper.screenshot("element")  # 儲存為 element.png

切換元素
--------

當 ``find_elements()`` 回傳多個元素時，使用 ``change_web_element()`` 切換活動元素：

.. code-block:: python

    # 切換到第 3 個元素（索引 2）
    web_element_wrapper.change_web_element(2)
    web_element_wrapper.click_element()

元素驗證
--------

.. code-block:: python

    web_element_wrapper.check_current_web_element({
        "tag_name": "input",
        "enabled": True
    })

方法參考
--------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - 方法
     - 參數
     - 說明
   * - ``click_element()``
     -
     - 點擊當前元素
   * - ``input_to_element()``
     - ``input_value: str``
     - 輸入文字到元素
   * - ``clear()``
     -
     - 清除元素內容
   * - ``submit()``
     -
     - 提交表單
   * - ``get_attribute()``
     - ``name: str``
     - 取得 HTML 屬性值
   * - ``get_property()``
     - ``name: str``
     - 取得 JavaScript 屬性值
   * - ``get_dom_attribute()``
     - ``name: str``
     - 取得 DOM 屬性值
   * - ``is_displayed()``
     -
     - 檢查元素是否可見
   * - ``is_enabled()``
     -
     - 檢查元素是否可用
   * - ``is_selected()``
     -
     - 檢查元素是否被選取
   * - ``value_of_css_property()``
     - ``property_name: str``
     - 取得 CSS 屬性值
   * - ``screenshot()``
     - ``filename: str``
     - 對元素截圖
   * - ``change_web_element()``
     - ``element_index: int``
     - 透過索引切換活動元素
   * - ``check_current_web_element()``
     - ``check_dict: dict``
     - 驗證元素屬性
   * - ``get_select()``
     -
     - 取得下拉選單的 Select 物件
