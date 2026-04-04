Logging
=======

Overview
--------

WebRunner uses Python's ``logging`` module with a rotating file handler
for logging automation events, errors, and warnings.

Configuration
-------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Property
     - Value
   * - Log file
     - ``WEBRunner.log``
   * - Log level
     - ``WARNING`` and above
   * - Max file size
     - 1 GB (rotating)
   * - Log format
     - ``%(asctime)s | %(name)s | %(levelname)s | %(message)s``
   * - Handler
     - ``RotatingFileHandler`` (custom ``WebRunnerLoggingHandler``)

Log Output
----------

The log file is created in the current working directory as ``WEBRunner.log``.
When the file reaches 1 GB, it is rotated.

Example log entries:

.. code-block:: text

    2025-01-01 12:00:00 | je_web_runner | WARNING | WebDriverWrapper find_element failed: ...
    2025-01-01 12:00:01 | je_web_runner | ERROR | WebdriverManager quit, failed: ...

Logger Instance
---------------

The global logger is accessible as ``web_runner_logger``:

.. code-block:: python

    from je_web_runner.utils.logging.loggin_instance import web_runner_logger

    web_runner_logger.warning("Custom warning message")

All WebRunner components use this logger internally to record their operations.
