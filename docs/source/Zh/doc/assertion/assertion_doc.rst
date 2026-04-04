斷言與驗證
==========

概述
----

WebRunner 提供斷言工具，用於在自動化過程中驗證 WebDriver 和 WebElement 的狀態。
驗證失敗時會引發 ``WebRunnerAssertException``。

WebDriver 驗證
---------------

.. code-block:: python

    # 透過 WebDriverWrapper
    wrapper.check_current_webdriver({"name": "chrome"})

.. code-block:: python

    # 透過工具函式
    from je_web_runner.utils.assert_value.result_check import (
        check_webdriver_value,
        check_webdriver_values,
    )

    check_webdriver_value("name", "chrome", webdriver_instance)
    check_webdriver_values({"name": "chrome"}, webdriver_instance)

WebElement 驗證
----------------

.. code-block:: python

    # 透過 WebElementWrapper
    web_element_wrapper.check_current_web_element({
        "tag_name": "input",
        "enabled": True
    })

.. code-block:: python

    # 透過工具函式
    from je_web_runner.utils.assert_value.result_check import check_web_element_details

    check_web_element_details(element, {
        "tag_name": "input",
        "enabled": True
    })

透過 Action Executor 使用
--------------------------

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_check_current_webdriver", {"check_dict": {"name": "chrome"}}],
        ["WR_quit"],
    ])
