安裝
====

透過 pip 安裝
--------------

**穩定版：**

.. code-block:: bash

    pip install je_web_runner

**開發版：**

.. code-block:: bash

    pip install je_web_runner_dev

系統需求
--------

* Python **3.10** 或更新版本
* pip **19.3** 或更新版本

相依套件（自動安裝）：

* ``selenium>=4.0.0``
* ``requests``
* ``python-dotenv``
* ``webdriver-manager``

支援平台
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 平台
     - 備註
   * - Windows 11
     - 完整支援
   * - macOS
     - 完整支援
   * - Ubuntu / Linux
     - 完整支援
   * - Raspberry Pi
     - 完整支援

支援瀏覽器
----------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - 瀏覽器
     - 代碼
     - 備註
   * - Google Chrome
     - ``chrome``
     - 最常使用，透過 webdriver-manager 自動管理
   * - Chromium
     - ``chromium``
     - 開源 Chrome 變體
   * - Mozilla Firefox
     - ``firefox``
     - 透過 GeckoDriver 完整支援
   * - Microsoft Edge
     - ``edge``
     - 基於 Chromium 的 Edge
   * - Internet Explorer
     - ``ie``
     - 舊版支援
   * - Apple Safari
     - ``safari``
     - 僅 macOS，無自動驅動程式管理

驗證安裝
--------

.. code-block:: python

    import je_web_runner
    print(je_web_runner.__all__)
