Selenium Utilities API
======================

Desired Capabilities
--------------------

``je_web_runner.utils.selenium_utils_wrapper.desired_capabilities.desired_capabilities``

.. code-block:: python

    def get_desired_capabilities_keys() -> dict_keys:
        """
        Get available WebDriver/browser names.

        :return: dict_keys of available browsers (e.g., 'CHROME', 'FIREFOX', 'EDGE', ...)
        """

    def get_desired_capabilities(webdriver_name: str) -> dict:
        """
        Get DesiredCapabilities for a specific browser.

        :param webdriver_name: browser name (e.g., "CHROME", "FIREFOX")
        :return: capabilities dict
        """

Keys
----

``je_web_runner.utils.selenium_utils_wrapper.keys.selenium_keys``

Re-export of ``selenium.webdriver.common.keys.Keys``.

Provides constants for special keyboard keys:

**Standard keys:**
``NULL``, ``CANCEL``, ``HELP``, ``BACKSPACE``, ``TAB``, ``CLEAR``,
``RETURN``, ``ENTER``, ``SHIFT``, ``LEFT_SHIFT``, ``CONTROL``, ``LEFT_CONTROL``,
``ALT``, ``LEFT_ALT``, ``PAUSE``, ``ESCAPE``, ``SPACE``,
``PAGE_UP``, ``PAGE_DOWN``, ``END``, ``HOME``,
``LEFT``, ``UP``, ``RIGHT``, ``DOWN``,
``INSERT``, ``DELETE``, ``SEMICOLON``, ``EQUALS``

**Number pad:**
``NUMPAD0`` through ``NUMPAD9``,
``MULTIPLY``, ``ADD``, ``SEPARATOR``, ``SUBTRACT``, ``DECIMAL``, ``DIVIDE``

**Function keys:**
``F1`` through ``F12``

**Special:**
``META``, ``COMMAND``, ``ZENKAKU_HANKAKU``
