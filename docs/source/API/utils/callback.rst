Callback API
============

``je_web_runner.utils.callback.callback_function_executor``

Class: CallbackFunctionExecutor
-------------------------------

Executes trigger functions with callback support.
Shares the same ``event_dict`` command mapping as the standard Executor.

.. code-block:: python

    class CallbackFunctionExecutor:

        event_dict: dict
            # Same command mapping as Executor (WR_* commands)

        def callback_function(
            self,
            trigger_function_name: str,
            callback_function: Callable,
            callback_function_param: Union[dict, list, None] = None,
            callback_param_method: str = "kwargs",
            **kwargs
        ):
            """
            Execute a trigger function, then execute a callback function.

            :param trigger_function_name: function name to trigger (must exist in event_dict)
            :param callback_function: callback function to execute after trigger
            :param callback_function_param: parameters for callback (dict for kwargs, list for args)
            :param callback_param_method: "kwargs" or "args"
            :param kwargs: parameters passed to the trigger function
            :return: return value of the trigger function
            :raises CallbackExecutorException: if trigger function not found or invalid param method
            """

Global Instance
---------------

.. code-block:: python

    callback_executor = CallbackFunctionExecutor()
