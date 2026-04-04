WebDriver 選項設定
==================

概述
----

在啟動 WebDriver 之前設定瀏覽器選項和功能。
適用於無頭模式、停用 GPU、設定視窗大小等。

瀏覽器參數
----------

.. code-block:: python

    from je_web_runner import set_webdriver_options_argument, get_webdriver_manager

    # 設定瀏覽器參數（回傳 Options 物件）
    options = set_webdriver_options_argument("chrome", [
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=1920,1080"
    ])

    # 或在建立管理器時直接傳入
    manager = get_webdriver_manager("chrome", options=["--headless", "--disable-gpu"])

常用 Chrome 參數
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 參數
     - 說明
   * - ``--headless``
     - 不顯示 GUI 執行
   * - ``--disable-gpu``
     - 停用 GPU 硬體加速
   * - ``--no-sandbox``
     - 停用沙箱（某些 Linux 環境需要）
   * - ``--window-size=W,H``
     - 設定初始視窗大小
   * - ``--incognito``
     - 以無痕模式開啟
   * - ``--start-maximized``
     - 以最大化視窗啟動

DesiredCapabilities
-------------------

.. code-block:: python

    from je_web_runner import get_desired_capabilities, get_desired_capabilities_keys

    # 檢視可用的功能鍵（瀏覽器名稱）
    keys = get_desired_capabilities_keys()

    # 取得特定瀏覽器的功能
    caps = get_desired_capabilities("CHROME")
