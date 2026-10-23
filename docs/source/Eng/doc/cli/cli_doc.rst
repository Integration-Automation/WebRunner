CLI Usage
=========

Overview
--------

WebRunner can be executed directly from the command line using the ``je_web_runner`` module.
Installing the package also installs the console scripts ``webrunner`` and
``web_runner``, which take the same flags and give the same output and exit
codes, so ``webrunner -e actions.json`` equals ``python -m je_web_runner -e
actions.json`` (``pipx run --spec je_web_runner webrunner`` works too).

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

A failed action does not stop its list: the remaining actions run, and so do the remaining files of
``-d``. Once everything has run, the process exits with code 1 and prints
``error: N action(s) or file(s) failed`` when anything failed, and with code 0 otherwise.

Running Under TestPioneer
-------------------------

TestPioneer starts a runner with ``TEST_PIONEER_ARTIFACT_DIR`` set to the directory that run's
output belongs in. A report asked for under a relative name (JSON, XML, HTML, JUnit, Allure,
interactive HTML, and ``generate_all_reports``) is then written below that directory, and the
folders it needs are created. An absolute name, and a name that would leave the directory, are
used as given. Without the variable nothing changes.

Local agent tasks
-----------------

``--agent-task task.json --report results/task`` runs a verified local task.
See :doc:`../integrations/local_agent_doc`.
