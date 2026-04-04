Exception Handling
==================

Overview
--------

WebRunner provides a hierarchy of custom exceptions for specific error scenarios.
All exceptions inherit from ``WebRunnerException``.

Exception Hierarchy
-------------------

.. code-block:: text

    WebRunnerException (base)
    ├── WebRunnerWebDriverNotFoundException
    ├── WebRunnerOptionsWrongTypeException
    ├── WebRunnerArgumentWrongTypeException
    ├── WebRunnerWebDriverIsNoneException
    ├── WebRunnerExecuteException
    ├── WebRunnerAssertException
    ├── WebRunnerHTMLException
    ├── WebRunnerAddCommandException
    ├── WebRunnerJsonException
    │   └── WebRunnerGenerateJsonReportException
    ├── XMLException
    │   └── XMLTypeException
    └── CallbackExecutorException

Exception Reference
-------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Exception
     - Description
   * - ``WebRunnerException``
     - Base exception for all WebRunner errors
   * - ``WebRunnerWebDriverNotFoundException``
     - WebDriver not found or browser name not supported
   * - ``WebRunnerOptionsWrongTypeException``
     - Invalid options type provided (must be list or set)
   * - ``WebRunnerArgumentWrongTypeException``
     - Invalid argument type provided
   * - ``WebRunnerWebDriverIsNoneException``
     - WebDriver is None (not initialized)
   * - ``WebRunnerExecuteException``
     - Error during action execution (unknown command, invalid format)
   * - ``WebRunnerJsonException``
     - JSON processing error
   * - ``WebRunnerGenerateJsonReportException``
     - JSON report generation error
   * - ``WebRunnerAssertException``
     - Assertion validation failure
   * - ``WebRunnerHTMLException``
     - HTML report generation error (e.g., no test records)
   * - ``WebRunnerAddCommandException``
     - Error registering custom command (not a function/method)
   * - ``XMLException``
     - XML processing error
   * - ``XMLTypeException``
     - Invalid XML type specified (must be ``"string"`` or ``"file"``)
   * - ``CallbackExecutorException``
     - Callback execution error (bad trigger function or method)

Example
-------

.. code-block:: python

    from je_web_runner import get_webdriver_manager
    from je_web_runner.utils.exception.exceptions import (
        WebRunnerException,
        WebRunnerWebDriverNotFoundException,
    )

    try:
        manager = get_webdriver_manager("unsupported_browser")
    except WebRunnerWebDriverNotFoundException as e:
        print(f"Browser not supported: {e}")
    except WebRunnerException as e:
        print(f"WebRunner error: {e}")
