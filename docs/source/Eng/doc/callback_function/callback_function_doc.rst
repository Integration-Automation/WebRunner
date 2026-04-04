Callback Executor
=================

Overview
--------

The Callback Executor allows you to execute automation commands with callback functions
triggered on completion. It wraps the standard executor's event dictionary and provides
an event-driven execution model.

The global instance ``callback_executor`` is imported from ``je_web_runner``.

Basic Usage
-----------

.. code-block:: python

    from je_web_runner import callback_executor

    def on_complete():
        print("Navigation complete!")

    callback_executor.callback_function(
        trigger_function_name="WR_to_url",
        callback_function=on_complete,
        url="https://example.com"
    )

The trigger function (``WR_to_url``) executes first, then the callback (``on_complete``) runs.

Callback with kwargs
--------------------

Pass keyword arguments to the callback using ``callback_param_method="kwargs"``:

.. code-block:: python

    def on_element_found(result=None):
        print(f"Element found: {result}")

    callback_executor.callback_function(
        trigger_function_name="WR_find_element",
        callback_function=on_element_found,
        callback_function_param={"result": "search_box"},
        callback_param_method="kwargs",
        element_name="search_box"
    )

Callback with args
------------------

Pass positional arguments using ``callback_param_method="args"``:

.. code-block:: python

    def on_done(msg):
        print(f"Done: {msg}")

    callback_executor.callback_function(
        trigger_function_name="WR_quit",
        callback_function=on_done,
        callback_function_param=["All browsers closed"],
        callback_param_method="args"
    )

Parameters
----------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Parameter
     - Type
     - Description
   * - ``trigger_function_name``
     - ``str``
     - Name of the function to trigger (must exist in ``event_dict``)
   * - ``callback_function``
     - ``Callable``
     - The callback function to execute after the trigger
   * - ``callback_function_param``
     - ``dict | list | None``
     - Parameters to pass to the callback
   * - ``callback_param_method``
     - ``str``
     - How to pass callback params: ``"kwargs"`` or ``"args"``
   * - ``**kwargs``
     -
     - Parameters passed to the trigger function

Return Value
------------

The ``callback_function()`` method returns the return value of the **trigger function**
(not the callback).

Adding Packages
---------------

You can add external packages to the callback executor:

.. code-block:: python

    from je_web_runner.utils.package_manager.package_manager_class import package_manager

    package_manager.add_package_to_callback_executor("time")

    # Now "time_sleep" is available as a trigger function name
