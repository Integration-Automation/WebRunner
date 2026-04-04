Package Manager
===============

Overview
--------

The Package Manager dynamically loads external Python packages into the executor at runtime.
This allows you to extend the executor's capabilities without modifying the source code.

When a package is added, all its public functions and classes are extracted and
registered in the executor's event dictionary with the naming convention ``{package}_{function}``.

Usage via Action Executor
-------------------------

.. code-block:: python

    from je_web_runner import execute_action

    actions = [
        # Load the 'time' package into executor
        ["WR_add_package_to_executor", {"package": "time"}],

        # Now you can use time.sleep as "time_sleep"
        ["time_sleep", [2]],
    ]

    execute_action(actions)

Direct API Usage
----------------

.. code-block:: python

    from je_web_runner.utils.package_manager.package_manager_class import package_manager

    # Check if a package exists and import it
    module = package_manager.check_package("os")

    # Add all functions from a package to the executor
    package_manager.add_package_to_executor("math")

    # Add to callback executor instead
    package_manager.add_package_to_callback_executor("time")

Methods
-------

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Method
     - Parameters
     - Description
   * - ``check_package()``
     - ``package: str``
     - Check and import a package, returns the module or None
   * - ``add_package_to_executor()``
     - ``package: str``
     - Add package members to the Executor's event_dict
   * - ``add_package_to_callback_executor()``
     - ``package: str``
     - Add package members to the CallbackExecutor's event_dict
   * - ``get_member()``
     - ``package, predicate, target``
     - Extract and add specific members from a package
   * - ``add_package_to_target()``
     - ``package: str, target``
     - Add functions/classes to a target executor

Naming Convention
-----------------

When a package is added, functions are registered with the prefix ``{package_name}_``.

For example, adding the ``time`` package registers:

* ``time_sleep`` -> ``time.sleep``
* ``time_time`` -> ``time.time``
* ``time_monotonic`` -> ``time.monotonic``
* etc.

Package Caching
---------------

The ``installed_package_dict`` attribute caches imported packages to avoid
re-importing them. If a package has already been loaded, subsequent calls
to ``check_package()`` return the cached module.
