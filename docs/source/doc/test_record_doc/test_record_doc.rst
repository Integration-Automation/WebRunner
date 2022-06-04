==================
WebRunner Test Record Doc
==================

.. code-block:: python

    """
    if you want to enable auto record use
    test_record_instance.set_record_enable(True)
    """

    def record_action_to_list(function_name: str, local_param: Union[vars, None],
                              program_exception: Union[Exception, None] = None):
        """
        normally not need self call this record but if you want to add something
        that want to record you cna use this
        :param function_name: what function call this method
        :param local_param: what param used
        :param program_exception: what exception happened
        :return: None
        """

