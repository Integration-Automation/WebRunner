Report Generation
=================

Overview
--------

WebRunner can automatically record all actions and generate reports in three formats:
**HTML**, **JSON**, and **XML**. Reports include detailed information about each executed action,
including function name, parameters, timestamp, and any exceptions.

.. note::

   Test recording must be enabled before generating reports.
   See the :doc:`../test_record/test_record_doc` section for details.

Enable Recording
----------------

.. code-block:: python

    from je_web_runner import test_record_instance

    test_record_instance.set_record_enable(True)

HTML Report
-----------

HTML reports include color-coded tables:

* **Aqua** background for successful actions
* **Red** background for failed actions

Each row shows: function name, parameters, timestamp, and exception (if any).

.. code-block:: python

    from je_web_runner import generate_html, generate_html_report

    # Generate HTML string (returns complete HTML document)
    html_content = generate_html()

    # Save to file (creates test_results.html)
    generate_html_report("test_results")

JSON Report
-----------

JSON reports produce separate files for success and failure records.

.. code-block:: python

    from je_web_runner import generate_json, generate_json_report

    # Generate dicts (returns tuple of success_dict, failure_dict)
    success_dict, failure_dict = generate_json()

    # Save to files:
    # - test_results_success.json
    # - test_results_failure.json
    generate_json_report("test_results")

XML Report
----------

.. code-block:: python

    from je_web_runner import generate_xml, generate_xml_report

    # Generate XML structures
    success_xml, failure_xml = generate_xml()

    # Save to files:
    # - test_results_success.xml
    # - test_results_failure.xml
    generate_xml_report("test_results")

Report via Action Executor
--------------------------

Reports can also be generated from action lists:

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        ["WR_set_record_enable", {"set_enable": True}],
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"],
        ["WR_generate_html_report", {"html_name": "my_report"}],
    ])

Record Data Format
------------------

Each record in the report contains:

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Field
     - Type
     - Description
   * - ``function_name``
     - ``str``
     - Name of the executed function
   * - ``local_param``
     - ``dict | None``
     - Parameters passed to the function
   * - ``time``
     - ``str``
     - Timestamp of execution
   * - ``program_exception``
     - ``str``
     - Exception message or ``"None"``

Thread Safety
-------------

All report generation methods use ``threading.Lock`` to ensure thread-safe file writing.
