測試物件
========

概述
----

``TestObject`` 封裝元素定位資訊（策略＋值），用於可重複使用的元素定義。
``TestObjectRecord`` 以名稱儲存 ``TestObject`` 實例，供 ``_with_test_object`` 方法使用。

建立測試物件
------------

.. code-block:: python

    from je_web_runner import TestObject, create_test_object, get_test_object_type_list

    # 建構子：TestObject(test_object_name, test_object_type)
    obj1 = TestObject("search", "name")

    # 工廠函式：create_test_object(object_type, test_object_name)
    obj2 = create_test_object("id", "submit-btn")

可用定位類型
------------

.. code-block:: python

    print(get_test_object_type_list())
    # ['ID', 'NAME', 'XPATH', 'CSS_SELECTOR', 'CLASS_NAME',
    #  'TAG_NAME', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']

這些直接對應 Selenium 的 ``By`` 類別常數。

TestObjectRecord
----------------

.. code-block:: python

    from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record

    # 儲存測試物件
    test_object_record.save_test_object("search_box", "name")

    # 移除測試物件
    test_object_record.remove_test_object("search_box")

    # 清除所有紀錄
    test_object_record.clean_record()

在 Action Executor 中使用
--------------------------

.. code-block:: python

    from je_web_runner import execute_action

    execute_action([
        ["WR_SaveTestObject", {"test_object_name": "search", "object_type": "name"}],
        ["WR_find_element", {"element_name": "search"}],
        ["WR_click_element"],
        ["WR_input_to_element", {"input_value": "hello"}],
        ["WR_CleanTestObject"],
    ])
