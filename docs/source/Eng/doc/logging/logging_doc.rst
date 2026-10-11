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
     - ``$WEBRUNNER_LOG_PATH`` (a full file path), else
       ``$WEBRUNNER_LOG_DIR/WEBRunner.log``, else
       ``~/.je_web_runner/logs/WEBRunner.log``
   * - Log level
     - ``WARNING`` and above
   * - Rotation
     - when a process opens a file over 10 MB, it is moved to ``<name>.1``
   * - Log format
     - ``%(asctime)s | %(process)d | %(name)s | %(levelname)s | %(message)s``
   * - Handler
     - ``RotatingFileHandler`` (custom ``WebRunnerLoggingHandler``)

Log Output
----------

Importing ``je_web_runner`` writes nothing: the file and its directory are
created on the first record, and the file is appended to, so processes of one
account can share it. A relative path resolves against the working directory at
import time; ``os.devnull`` turns the file off. A file that cannot be opened is
replaced by ``os.devnull`` with one ``RuntimeWarning``.

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
