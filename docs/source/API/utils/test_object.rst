Test Object API
===============

``je_web_runner.utils.test_object.test_object_class``

Class: TestObject
-----------------

.. code-block:: python

    class TestObject:
        """
        Encapsulates element locator information.

        Attributes:
            test_object_type (str): locator strategy (e.g., "name", "id", "xpath")
            test_object_name (str): locator value (e.g., "search", "//div[@id='main']")
        """

        def __init__(self, test_object_name: str, test_object_type: str):
            ...

Functions
---------

.. code-block:: python

    def create_test_object(object_type: str, test_object_name: str) -> TestObject:
        """
        Factory function to create a TestObject.

        :param object_type: locator strategy (must be in type_list)
        :param test_object_name: locator value
        :return: TestObject instance
        """

    def get_test_object_type_list() -> list:
        """
        Get available locator types from selenium.webdriver.common.by.By.

        :return: list of type strings
            ['ID', 'NAME', 'XPATH', 'CSS_SELECTOR', 'CLASS_NAME',
             'TAG_NAME', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']
        """

TestObjectRecord
----------------

``je_web_runner.utils.test_object.test_object_record.test_object_record_class``

.. code-block:: python

    class TestObjectRecord:
        """
        Stores TestObject instances by name for later retrieval.
        Used by _with_test_object methods and the Action Executor.

        Attributes:
            test_object_record_dict (dict): {name: TestObject} storage
        """

        def save_test_object(self, test_object_name: str, object_type: str) -> None:
            """Save a TestObject by name."""

        def remove_test_object(self, test_object_name: str) -> Union[TestObject, bool]:
            """Remove and return a TestObject by name. Returns False if not found."""

        def clean_record(self) -> None:
            """Clear all stored TestObjects."""

Global Instance
~~~~~~~~~~~~~~~

.. code-block:: python

    test_object_record = TestObjectRecord()
