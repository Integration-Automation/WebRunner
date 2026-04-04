CLI Usage
=========

Overview
--------

WebRunner can be executed directly from the command line using the ``je_web_runner`` module.

Commands
--------

**Execute a single JSON action file:**

.. code-block:: bash

    python -m je_web_runner -e actions.json
    python -m je_web_runner --execute_file actions.json

**Execute all JSON files in a directory:**

.. code-block:: bash

    python -m je_web_runner -d ./actions/
    python -m je_web_runner --execute_dir ./actions/

**Execute a JSON action string directly:**

.. code-block:: bash

    python -m je_web_runner --execute_str '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_quit"]]'

Command Reference
-----------------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Flag
     - Short
     - Description
   * - ``--execute_file``
     - ``-e``
     - Execute a single JSON action file
   * - ``--execute_dir``
     - ``-d``
     - Execute all JSON files in a directory
   * - ``--execute_str``
     -
     - Execute a JSON action string directly

JSON File Format
----------------

The JSON file should contain an array of action lists:

.. code-block:: json

    [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]

.. note::

   On Windows, the ``--execute_str`` option may require double JSON parsing
   due to shell escaping. WebRunner handles this automatically.

Error Handling
--------------

If no arguments are provided, WebRunner raises a ``WebRunnerExecuteException``.
All errors are printed to stderr and the process exits with code 1.
