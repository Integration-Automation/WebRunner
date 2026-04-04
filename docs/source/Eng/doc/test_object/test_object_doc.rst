Test Object
===========

Overview
--------

``TestObject`` encapsulates element locator information (strategy + value) for reusable element definitions.
``TestObjectRecord`` stores ``TestObject`` instances by name for later retrieval by the ``_with_test_object`` methods.

Creating Test Objects
---------------------

.. code-block:: python

    from je_web_runner import TestObject, create_test_object, get_test_object_type_list

    # Constructor: TestObject(test_object_name, test_object_type)
    obj1 = TestObject("search", "name")

    # Factory function: create_test_object(object_type, test_object_name)
    obj2 = create_test_object("id", "submit-btn")

Available Locator Types
-----------------------

.. code-block:: python

    print(get_test_object_type_list())
    # ['ID', 'NAME', 'XPATH', 'CSS_SELECTOR', 'CLASS_NAME',
    #  'TAG_NAME', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']

These map directly to Selenium's ``By`` class constants.

TestObject Attributes
---------------------

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Attribute
     - Type
     - Description
   * - ``test_object_type``
     - ``str``
     - Locator strategy (e.g., ``"name"``, ``"xpath"``)
   * - ``test_object_name``
     - ``str``
     - Locator value (e.g., ``"search"``, ``"//div[@id='main']"``)

TestObjectRecord
----------------

``TestObjectRecord`` stores ``TestObject`` instances by name. This is used by the Action Executor
to reference elements by string names (e.g., ``WR_SaveTestObject`` and ``WR_find_element``).

.. code-block:: python

    from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record

    # Save a test object
    test_object_record.save_test_object("search_box", "name")

    # Remove a test object
    test_object_record.remove_test_object("search_box")

    # Clear all records
    test_object_record.clean_record()

Usage in Action Executor
------------------------

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        # Save a test object with name "search" and locator type "name"
        ["WR_SaveTestObject", {"test_object_name": "search", "object_type": "name"}],

        # Find the element by its saved name
        ["WR_find_element", {"element_name": "search"}],

        # Interact with the found element
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "hello"}],

        # Clean all saved test objects
        ["WR_CleanTestObject"],
    ])
