Package Manager API
===================

``je_web_runner.utils.package_manager.package_manager_class``

Class: PackageManager
---------------------

Dynamically imports Python packages and registers their functions/classes
into the Executor or CallbackExecutor event dictionaries.

.. code-block:: python

    class PackageManager:

        installed_package_dict: dict
            # Cache of imported packages {name: module}

        executor: Executor
            # Reference to the global Executor instance

        callback_executor: CallbackFunctionExecutor
            # Reference to the global CallbackFunctionExecutor instance

        def check_package(self, package: str):
            """
            Check if a package exists and import it.

            :param package: package name to check
            :return: imported module if found, None otherwise
            """

        def add_package_to_executor(self, package: str) -> None:
            """
            Add all functions and classes from a package to the Executor's event_dict.
            Functions are registered as "{package}_{function_name}".

            :param package: package name to import and register
            """

        def add_package_to_callback_executor(self, package: str) -> None:
            """
            Add all functions and classes from a package to the CallbackExecutor's event_dict.

            :param package: package name to import and register
            """

        def get_member(self, package: str, predicate, target) -> None:
            """
            Extract members matching a predicate and add them to a target executor.

            :param package: package name
            :param predicate: inspect predicate (isfunction, isbuiltin, isclass)
            :param target: executor instance with event_dict attribute
            """

        def add_package_to_target(self, package: str, target) -> None:
            """
            Add functions, builtins, and classes from a package to a target executor.

            :param package: package name
            :param target: executor instance with event_dict attribute
            """

Global Instance
---------------

.. code-block:: python

    package_manager = PackageManager()
