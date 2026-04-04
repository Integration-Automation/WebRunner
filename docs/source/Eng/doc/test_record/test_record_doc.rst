Test Record
===========

Overview
--------

All WebRunner actions can be automatically recorded for audit trails and report generation.
The global instance ``test_record_instance`` manages recording state and stores records.

Enable Recording
----------------

Recording is disabled by default. Enable it before running actions:

.. code-block:: python

    from je_web_runner import test_record_instance

    test_record_instance.set_record_enable(True)

Or via the action executor:

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        ["WR_set_record_enable", {"set_enable": True}],
        # ... your actions ...
    ])

Accessing Records
-----------------

.. code-block:: python

    from je_web_runner import test_record_instance

    test_record_instance.set_record_enable(True)

    # ... perform automation ...

    # Access records
    records = test_record_instance.test_record_list

    for record in records:
        print(record)

Record Format
-------------

Each record is a dictionary with the following fields:

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
     - Timestamp of execution (e.g., ``"2025-01-01 12:00:00"``)
   * - ``program_exception``
     - ``str``
     - Exception message or ``"None"`` if successful

Example record:

.. code-block:: python

    {
        "function_name": "to_url",
        "local_param": {"url": "https://example.com"},
        "time": "2025-01-01 12:00:00",
        "program_exception": "None"
    }

Clearing Records
----------------

.. code-block:: python

    test_record_instance.clean_record()

Attributes
----------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Attribute
     - Type
     - Description
   * - ``test_record_list``
     - ``list``
     - List of all recorded actions
   * - ``init_record``
     - ``bool``
     - Whether recording is currently enabled
