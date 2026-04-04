WebDriver 管理器
=================

概述
----

``WebdriverManager`` 管理多個 WebDriver 實例以支援並行瀏覽器自動化。
它維護一個活動 WebDriver 清單，並提供建立、切換和關閉的方法。

透過工廠函式 ``get_webdriver_manager()`` 取得管理器。

建立管理器
----------

.. code-block:: python

    from je_web_runner import get_webdriver_manager

    # 使用 Chrome 建立
    manager = get_webdriver_manager("chrome")

    # 使用 Firefox 搭配選項建立
    manager = get_webdriver_manager("firefox", options=["--headless"])

管理多個瀏覽器
--------------

.. code-block:: python

    manager = get_webdriver_manager("chrome")

    # 新增第二個瀏覽器實例
    manager.new_driver("firefox")

    # 切換到 Chrome（索引 0）
    manager.change_webdriver(0)
    manager.webdriver_wrapper.to_url("https://example.com")

    # 切換到 Firefox（索引 1）
    manager.change_webdriver(1)
    manager.webdriver_wrapper.to_url("https://google.com")

    # 僅關閉 Firefox
    manager.close_choose_webdriver(1)

    # 關閉當前瀏覽器
    manager.close_current_webdriver()

    # 關閉並退出所有瀏覽器
    manager.quit()

關鍵屬性
--------

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - 屬性
     - 型別
     - 說明
   * - ``webdriver_wrapper``
     - ``WebDriverWrapper``
     - WebDriver 操作包裝器
   * - ``webdriver_element``
     - ``WebElementWrapper``
     - 元素操作包裝器
   * - ``current_webdriver``
     - ``WebDriver | None``
     - 當前活動的 WebDriver 實例

方法
----

.. list-table::
   :header-rows: 1
   :widths: 30 40 30

   * - 方法
     - 參數
     - 說明
   * - ``new_driver()``
     - ``webdriver_name: str, options: List[str] = None, **kwargs``
     - 建立新的 WebDriver 實例
   * - ``change_webdriver()``
     - ``index_of_webdriver: int``
     - 透過索引切換 WebDriver
   * - ``close_current_webdriver()``
     -
     - 關閉當前 WebDriver
   * - ``close_choose_webdriver()``
     - ``webdriver_index: int``
     - 透過索引關閉指定 WebDriver
   * - ``quit()``
     -
     - 關閉並退出所有 WebDriver

.. note::

   呼叫 ``quit()`` 時，會同時清除所有已儲存的 ``TestObjectRecord`` 項目。
