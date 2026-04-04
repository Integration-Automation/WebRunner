JSON Utilities API
==================

JSON File Operations
--------------------

``je_web_runner.utils.json.json_file.json_file``

.. code-block:: python

    def read_action_json(json_file_path: str) -> list:
        """
        Read an action JSON file and return its contents.
        Thread-safe (uses threading.Lock).

        :param json_file_path: path to the JSON file
        :return: list of actions parsed from the file
        :raises WebRunnerJsonException: if reading or parsing fails
        """

    def write_action_json(json_save_path: str, action_json: list) -> None:
        """
        Write an action list to a JSON file with indentation.
        Thread-safe (uses threading.Lock).

        :param json_save_path: path to save the JSON file
        :param action_json: list of actions to write
        """

JSON Formatting
---------------

``je_web_runner.utils.json.json_format.json_process``

.. code-block:: python

    def reformat_json(json_string: str, **kwargs) -> str:
        """
        Reformat a JSON string with indentation (pretty-print).

        :param json_string: valid JSON string to reformat
        :param kwargs: additional kwargs passed to json.dumps
        :return: reformatted JSON string
        :raises WebRunnerJsonException: if the string is not valid JSON
        """
