WebDriver Options Configuration
================================

Overview
--------

Configure browser options and capabilities before launching a WebDriver instance.
This is useful for headless mode, disabling GPU, setting window size, etc.

Browser Arguments
-----------------

.. code-block:: python

    from je_web_runner import set_webdriver_options_argument, get_webdriver_manager

    # Set browser arguments (returns Options object)
    options = set_webdriver_options_argument("chrome", [
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--window-size=1920,1080"
    ])

    # Or pass options directly when creating the manager
    manager = get_webdriver_manager("chrome", options=["--headless", "--disable-gpu"])

Common Chrome Arguments
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Argument
     - Description
   * - ``--headless``
     - Run without visible GUI
   * - ``--disable-gpu``
     - Disable GPU hardware acceleration
   * - ``--no-sandbox``
     - Disable sandbox (required in some Linux environments)
   * - ``--window-size=W,H``
     - Set initial window size
   * - ``--incognito``
     - Open in incognito mode
   * - ``--disable-extensions``
     - Disable browser extensions
   * - ``--start-maximized``
     - Start with maximized window

DesiredCapabilities
-------------------

.. code-block:: python

    from je_web_runner import get_desired_capabilities, get_desired_capabilities_keys

    # View available capability keys (browser names)
    keys = get_desired_capabilities_keys()
    # dict_keys(['CHROME', 'FIREFOX', 'EDGE', ...])

    # Get capabilities for a specific browser
    caps = get_desired_capabilities("CHROME")

Setting Capabilities via Wrapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from je_web_runner.webdriver.webdriver_with_options import set_webdriver_options_capability_wrapper

    options = set_webdriver_options_capability_wrapper("chrome", {
        "acceptInsecureCerts": True
    })

Functions Reference
-------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Function
     - Description
   * - ``set_webdriver_options_argument(webdriver_name, argument_iterable)``
     - Set browser startup arguments; returns ``Options`` object
   * - ``set_webdriver_options_capability_wrapper(webdriver_name, key_and_vale_dict)``
     - Set browser capabilities; returns ``Options`` object
   * - ``get_desired_capabilities_keys()``
     - Get available browser names
   * - ``get_desired_capabilities(webdriver_name)``
     - Get DesiredCapabilities dict for a browser
