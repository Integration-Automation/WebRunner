Installation
============

Install via pip
---------------

**Stable version:**

.. code-block:: bash

    pip install je_web_runner

**Development version:**

.. code-block:: bash

    pip install je_web_runner_dev

Requirements
------------

* Python **3.10** or later
* pip **19.3** or later

Dependencies (installed automatically):

* ``selenium>=4.0.0``
* ``requests``
* ``python-dotenv``
* ``webdriver-manager``

Supported Platforms
-------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Platform
     - Notes
   * - Windows 11
     - Fully supported
   * - macOS
     - Fully supported
   * - Ubuntu / Linux
     - Fully supported
   * - Raspberry Pi
     - Fully supported

Supported Browsers
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 20 50

   * - Browser
     - Key
     - Notes
   * - Google Chrome
     - ``chrome``
     - Most commonly used, auto-managed via webdriver-manager
   * - Chromium
     - ``chromium``
     - Open-source Chrome variant
   * - Mozilla Firefox
     - ``firefox``
     - Full support via GeckoDriver
   * - Microsoft Edge
     - ``edge``
     - Chromium-based Edge
   * - Internet Explorer
     - ``ie``
     - Legacy support
   * - Apple Safari
     - ``safari``
     - macOS only, no auto driver management

Verify Installation
-------------------

.. code-block:: python

    import je_web_runner
    print(je_web_runner.__all__)
