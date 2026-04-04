WebDriver 包裝器
=================

概述
----

``WebDriverWrapper`` 是核心元件，包裝了 Selenium WebDriver 並提供全面的方法。
涵蓋瀏覽器控制、元素尋找、滑鼠／鍵盤操作、Cookie 管理、JavaScript 執行、視窗管理等功能。

導航
----

.. code-block:: python

    wrapper = manager.webdriver_wrapper

    wrapper.to_url("https://example.com")    # 導航至網址
    wrapper.forward()                        # 前進
    wrapper.back()                           # 後退
    wrapper.refresh()                        # 重新整理

元素尋找
--------

使用 ``TestObject`` 定位器尋找元素：

.. code-block:: python

    from je_web_runner import TestObject

    # 定位策略：id, name, xpath, css selector,
    # class name, tag name, link text, partial link text
    element = TestObject("search-input", "id")

    wrapper.find_element(element)       # 尋找單一元素
    wrapper.find_elements(element)      # 尋找多個元素

使用已儲存的 ``TestObjectRecord`` 名稱尋找：

.. code-block:: python

    wrapper.find_element_with_test_object_record("search-input")
    wrapper.find_elements_with_test_object_record("search-input")

等待方法
--------

.. code-block:: python

    wrapper.implicitly_wait(5)           # 隱式等待（秒）
    wrapper.explict_wait(                # 顯式等待
        wait_condition,
        timeout=10,
        poll_frequency=0.5
    )
    wrapper.set_script_timeout(30)       # 非同步腳本逾時
    wrapper.set_page_load_timeout(60)    # 頁面載入逾時

滑鼠操作
--------

**基本點擊（於當前位置）：**

.. code-block:: python

    wrapper.left_click()
    wrapper.right_click()
    wrapper.left_double_click()
    wrapper.left_click_and_hold()
    wrapper.release()

**對已儲存的測試物件點擊：**

.. code-block:: python

    wrapper.left_click_with_test_object("button_name")
    wrapper.right_click_with_test_object("button_name")
    wrapper.left_double_click_with_test_object("button_name")
    wrapper.left_click_and_hold_with_test_object("button_name")
    wrapper.release_with_test_object("button_name")

**拖放：**

.. code-block:: python

    wrapper.drag_and_drop(source_element, target_element)
    wrapper.drag_and_drop_offset(element, x=100, y=50)

    # 使用已儲存的測試物件
    wrapper.drag_and_drop_with_test_object("source_name", "target_name")
    wrapper.drag_and_drop_offset_with_test_object("element_name", offset_x=100, offset_y=50)

**滑鼠移動：**

.. code-block:: python

    wrapper.move_to_element(element)             # 懸停
    wrapper.move_to_element_with_test_object("element_name")
    wrapper.move_to_element_with_offset(element, offset_x=10, offset_y=10)
    wrapper.move_to_element_with_offset_and_test_object("name", offset_x=10, offset_y=10)
    wrapper.move_by_offset(100, 200)             # 從當前位置移動

鍵盤操作
--------

.. code-block:: python

    wrapper.press_key(keycode)
    wrapper.press_key_with_test_object(keycode)
    wrapper.release_key(keycode)
    wrapper.release_key_with_test_object(keycode)
    wrapper.send_keys("text")
    wrapper.send_keys_to_element(element, "text")
    wrapper.send_keys_to_element_with_test_object("element_name", "text")

動作鏈控制
----------

.. code-block:: python

    wrapper.perform()          # 執行佇列中的動作
    wrapper.reset_actions()    # 清除動作佇列
    wrapper.pause(2)           # 在動作鏈中暫停（秒）
    wrapper.scroll(0, 500)     # 捲動頁面

Cookie 管理
-----------

.. code-block:: python

    wrapper.get_cookies()                              # 取得所有 Cookie
    wrapper.get_cookie("session_id")                   # 取得指定 Cookie
    wrapper.add_cookie({"name": "key", "value": "val"})
    wrapper.delete_cookie("session_id")
    wrapper.delete_all_cookies()

JavaScript 執行
----------------

.. code-block:: python

    wrapper.execute("document.title")
    wrapper.execute_script("return document.title")
    wrapper.execute_async_script("arguments[0]('done')", callback)

視窗管理
--------

.. code-block:: python

    wrapper.maximize_window()
    wrapper.minimize_window()
    wrapper.fullscreen_window()
    wrapper.set_window_size(1920, 1080)
    wrapper.set_window_position(0, 0)
    wrapper.get_window_position()       # 回傳 dict
    wrapper.get_window_rect()           # 回傳 dict
    wrapper.set_window_rect(x=0, y=0, width=1920, height=1080)

截圖
----

.. code-block:: python

    wrapper.get_screenshot_as_png()       # 回傳 bytes
    wrapper.get_screenshot_as_base64()    # 回傳 base64 字串

Frame／視窗／Alert 切換
------------------------

.. code-block:: python

    wrapper.switch("frame", "frame_name")
    wrapper.switch("window", "window_handle")
    wrapper.switch("default_content")
    wrapper.switch("parent_frame")
    wrapper.switch("active_element")
    wrapper.switch("alert")

瀏覽器日誌
----------

.. code-block:: python

    wrapper.get_log("browser")

WebDriver 驗證
---------------

.. code-block:: python

    wrapper.check_current_webdriver({"name": "chrome"})
