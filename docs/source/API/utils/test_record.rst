Test Record API
===============

``je_web_runner.utils.test_record.test_record_class``

Class: TestRecord
-----------------

.. code-block:: python

    class TestRecord:
        """
        Manages recording of test actions for audit and report generation.

        Attributes:
            test_record_list (list): list of recorded action dicts
            init_record (bool): whether recording is enabled (default: False)
        """

        def set_record_enable(self, set_enable: bool = True) -> None:
            """
            Enable or disable test recording.

            :param set_enable: True to enable, False to disable
            """

        def clean_record(self) -> None:
            """Clear all recorded actions."""

Function: record_action_to_list
-------------------------------

.. code-block:: python

    def record_action_to_list(
        function_name: str,
        local_param: Union[dict, None],
        program_exception: Union[Exception, None] = None
    ) -> None:
        """
        Record a function execution to the global test_record_instance.

        Each record is a dict:
        {
            "function_name": str,
            "local_param": dict or None,
            "time": str (timestamp),
            "program_exception": str ("None" or exception repr)
        }

        :param function_name: name of the executed function
        :param local_param: parameters passed to the function
        :param program_exception: exception that occurred (None if success)
        """

Global Instance
---------------

.. code-block:: python

    test_record_instance = TestRecord()
