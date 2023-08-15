.. code-block:: python

    def record_action_to_list(function_name: str, local_param: Union[vars, None],
                              program_exception: Union[Exception, None] = None):
        """
        :param function_name: what function call this method
        :param local_param: what param used
        :param program_exception: what exception happened
        :return: None
        """