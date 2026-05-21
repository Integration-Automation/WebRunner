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

進階啟動參數
------------

``set_driver`` 除了 CLI 參數外還支援三個選用參數：

.. code-block:: python

    wrapper.set_driver(
        "chrome",
        options=["--disable-blink-features=AutomationControlled"],
        experimental_options={                          # 僅 Chromium 系
            "excludeSwitches": ["enable-automation"],
            "useAutomationExtension": False,
            "prefs": {"download.default_directory": "/tmp"},
        },
        extension_paths=["/path/to/extension.crx"],     # add_extension
        enable_bidi=True,                               # webSocketUrl capability
    )

附加到已啟動的瀏覽器（以 ``--remote-debugging-port=9222`` 開啟）：

.. code-block:: python

    wrapper.attach_to_existing_browser("127.0.0.1:9222")

頁面 / 視窗 metadata
--------------------

.. code-block:: python

    wrapper.get_current_url()              # → str
    wrapper.get_title()
    wrapper.get_page_source()
    wrapper.get_window_handles()           # → list[str]
    wrapper.get_current_window_handle()
    wrapper.new_window("tab")              # 或 "window"
    wrapper.close_window()                 # 僅關當前 tab；要結束整個 driver 用 quit()

依子字串切換 tab（找不到時自動還原原視窗）：

.. code-block:: python

    wrapper.switch_to_window_by_url("checkout")
    wrapper.switch_to_window_by_title("結帳")

重整 / 捲動 / 視窗置頂
----------------------

.. code-block:: python

    wrapper.reload(ignore_cache=False)     # ignore_cache=True → CDP Page.reload (Ctrl+Shift+R)
    wrapper.scroll_to_element(element)     # JS scrollIntoView({block:'center'})
    wrapper.scroll_to_top(); wrapper.scroll_to_bottom()
    wrapper.bring_to_front()               # CDP Page.bringToFront

截圖與 PDF
----------

.. code-block:: python

    wrapper.save_screenshot("./shot.png")              # → bool
    wrapper.save_full_page_screenshot("./full.png")    # CDP captureBeyondViewport
    wrapper.print_page("./page.pdf")                   # Selenium 4 print_page
    wrapper.get_screenshot_as_png()                    # → bytes (沿用)
    wrapper.get_screenshot_as_base64()                 # → str (沿用)

Session 持久化
--------------

.. code-block:: python

    wrapper.to_url("https://example.com/")
    # … 完成登入 …
    wrapper.save_cookies("./cookies.json")             # → bool

    # 重啟瀏覽器後：
    wrapper.to_url("https://example.com/")
    added = wrapper.load_cookies("./cookies.json")     # → int (成功套用的數量)

    wrapper.clear_origin_storage("https://example.com")  # cookies + localStorage + IDB + cache

CDP 便利方法（僅 Chromium 系）
------------------------------

.. code-block:: python

    wrapper.execute_cdp_cmd("Page.bringToFront")
    wrapper.add_script_to_evaluate_on_new_document(
        "Object.defineProperty(navigator, 'webdriver', {get:()=>undefined});"
    )
    wrapper.set_user_agent("Mozilla/5.0 (custom)")
    wrapper.set_extra_http_headers({"X-Run": "ci-123"})
    wrapper.set_geolocation(35.68, 139.69, accuracy=50)
    wrapper.clear_geolocation_override()

    wrapper.set_timezone("Asia/Tokyo")
    wrapper.set_locale("ja-JP")
    wrapper.set_device_metrics(390, 844, device_scale_factor=3, mobile=True)
    wrapper.clear_device_metrics()

    wrapper.set_network_conditions(
        offline=False, latency=200,
        download_throughput=50_000, upload_throughput=10_000,
    )
    wrapper.block_urls(["*.doubleclick.net/*"])
    wrapper.unblock_urls()
    wrapper.set_cache_disabled(True)
    wrapper.set_download_directory("./downloads")    # headless 下載必備

CDP Fetch 攔截
--------------

``Fetch.*`` CDP 命令薄包裝。要實際收事件 (``Fetch.requestPaused``) 請使用
``CDPEventListener``（或 Selenium trio-based devtools listener）自行訂閱：

.. code-block:: python

    wrapper.enable_fetch_interception(patterns=["*/api/*"])
    # 在事件 callback 中：
    wrapper.continue_request(req_id, url=rewritten, method="POST",
                              post_data="...", headers={"X-Test": "1"})
    wrapper.fulfill_request(req_id, response_code=200,
                             body=b'{"ok": true}',
                             response_headers={"Content-Type": "application/json"})
    wrapper.fail_request(req_id, error_reason="AccessDenied")
    wrapper.disable_fetch_interception()

W3C BiDi 事件 listener
----------------------

需 Selenium 4.16+ 且以 ``enable_bidi=True`` 啟動：

.. code-block:: python

    wrapper.set_driver("chrome", enable_bidi=True)
    sub = wrapper.add_console_listener(lambda entry: print(entry.text))
    err = wrapper.add_js_error_listener(lambda e: print("exception:", e))
    wrapper.remove_console_listener(sub)
    wrapper.remove_js_error_listener(err)

未啟用 BiDi 時呼叫會丟出 ``WebRunnerException`` 並附上修復指引。

獨立 CDP / BiDi 模組
--------------------

``CDPEventListener`` (``je_web_runner.utils.cdp.event_loop``) 在背景開
WebSocket，讓命令與事件共用同一個 target session：

.. code-block:: python

    from je_web_runner import CDPEventListener

    with CDPEventListener.from_driver(driver) as listener:
        listener.on("Fetch.requestPaused", on_paused)
        listener.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

需 ``pip install websocket-client``；缺套件會丟 ``CDPEventLoopError``。

Performance tracing：

.. code-block:: python

    from je_web_runner import record_trace

    record_trace(
        driver, "perf.json",
        categories=["devtools.timeline", "loading"],
        duration=10.0,
    )
    # 用 chrome://tracing 或 DevTools「Performance」面板開啟 perf.json。

跨瀏覽器 BiDi network (Chrome / Edge / Firefox)：

.. code-block:: python

    from je_web_runner import (
        bidi_add_request_handler,
        bidi_add_response_handler,
        bidi_add_auth_handler,
        bidi_clear_network_handlers,
    )

    sub = bidi_add_request_handler(driver, lambda req: print(req.url))
    bidi_clear_network_handlers(driver)

Action JSON 別名
----------------

以上所有方法都有對應的 ``WR_*`` 別名（``WR_set_timezone`` /
``WR_save_cookies`` / ``WR_enable_fetch_interception`` /
``WR_save_full_page_screenshot`` / ``WR_attach_to_existing_browser`` ……），
所以 MCP server 的 ``webrunner_run_actions`` 工具也能直接驅動。

內部 mixin 拆分
---------------

``WebDriverWrapper`` 現以 mixin 組合，位於
``je_web_runner/webdriver/_wrapper_mixins/`` 之下，確保每個檔案不超過專案
規範的 750 行：

* ``_scripting_mixin.py`` — ``execute`` / ``execute_script`` /
  ``execute_async_script`` / ``execute_cdp_cmd``、全部 CDP 便利方法、
  Fetch 原語、BiDi listener
* ``_navigation_mixin.py`` — 導航、scroll、``switch``、視窗 / tab 管理、
  視窗大小位置
* ``_cookie_mixin.py`` — cookies + ``save_cookies`` / ``load_cookies`` /
  ``clear_origin_storage``
* ``_actions_mixin.py`` — ActionChains 全集
* ``_media_mixin.py`` — 截圖、``print_page``、``get_log``

組合後的類別本體、driver 生命週期 (``set_driver``、
``attach_to_existing_browser``、``quit``)、元素查找、等待都留在
``webdriver_wrapper.py``。對外的 import (``webdriver_wrapper_instance``、
``WebDriverWrapper``) 完全不變。
