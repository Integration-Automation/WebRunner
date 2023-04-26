Json File API
----

.. code-block:: python

    def read_action_json(json_file_path: str) -> list:
        """
        read the action json
        :param json_file_path json file's path to read
        """

    def write_action_json(json_save_path: str, action_json: list):
        """
        write action json
        :param json_save_path  json save path
        :param action_json the json str include action to write
        """

    def __process_json(json_string: str, **kwargs) -> str:
        """
        :param json_string: full json str (not json type)
        :param kwargs: any another kwargs for dumps
        :return: reformat str
        """

    def reformat_json(json_string: str, **kwargs) -> str:
        """
        :param json_string: Valid json string
        :param kwargs: __process_json params
        :return: reformat json string
        """