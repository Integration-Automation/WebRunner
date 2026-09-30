========
Backends
========

Selenium（預設）
================

原本的 ``WebDriverWrapper`` 與 ``WebElementWrapper``。所有沒有特定前綴的
命令都會走這條。

Playwright
==========

Playwright 後端的命令前綴為 ``WR_pw_*``，採 opt-in 設計：既有腳本可繼續跑在
Selenium 上。它涵蓋大部分日常操作，但不是 Selenium 命令面的一對一複本。下面
的表格先列出對應的命令與差異，再列出只有其中一個後端才有的功能。

* lifecycle / 分頁 / 導覽。網站自己開的分頁（popup、``window.open``）也會被
  追蹤，``WR_pw_switch_to_page`` 可以切過去。
* find（含 ``TestObject`` 自動翻譯）與直接的 page-level 快捷。快捷命令會把
  額外的 Playwright 選項原樣傳下去（``button``、``modifiers``、``timeout``、
  ``force``、``wait_until`` …）。
* 元素層 wrapper
* 行動裝置模擬、locale、時區、地理位置、權限、clock
* HAR 錄製、route mock、console + 網路事件擷取
* 透過 CDP 的網路節流預設集

page-level 的動作會寫進測試紀錄，所以和 Selenium 的步驟一樣會出現在產生的
報告裡。

對應的命令
----------

.. list-table::
   :header-rows: 1
   :widths: 16 30 30 24

   * - 工作
     - Selenium
     - Playwright
     - 差異
   * - 啟動 / 結束
     - ``WR_get_webdriver_manager``（``WR_new_driver``）、``WR_quit``
     - ``WR_pw_launch``、``WR_pw_quit``
     - Playwright 跑 Chromium、Firefox 或 WebKit，同一時間一個瀏覽器、一個
       context。
   * - 導覽
     - ``WR_to_url``、``WR_back``、``WR_forward``、``WR_refresh``
     - ``WR_pw_to_url``、``WR_pw_back``、``WR_pw_forward``、``WR_pw_refresh``
     - ``WR_pw_to_url`` 接受 ``goto`` 的選項，例如 ``wait_until``。
   * - 頁面資訊
     - ``WR_get_current_url``、``WR_get_title``、``WR_get_page_source``
     - ``WR_pw_url``、``WR_pw_title``、``WR_pw_content``
     - 只有名稱不同。
   * - 找已記錄的 ``TestObject``
     - ``WR_find_recorded_element``、``WR_find_recorded_elements``
     - ``WR_pw_find_element_with_test_object_record``、
       ``WR_pw_find_elements_with_test_object_record``
     - ``TestObject`` 會翻譯成 Playwright selector。
   * - 點擊、懸停
     - ``WR_element_click``；``WR_left_click`` / ``WR_move_to_element``
       再 ``WR_perform``
     - ``WR_pw_element_click`` / ``WR_pw_element_hover``，或帶 selector 的
       ``WR_pw_click`` / ``WR_pw_hover``
     - Selenium 的 ActionChains 命令會排隊到 ``WR_perform`` 才執行；
       Playwright 立即執行。
   * - 輸入
     - ``WR_element_input``
     - ``WR_pw_element_type_text``、``WR_pw_element_fill``
     - ``WR_element_input`` 與 ``type_text`` 是附加；``fill`` 會取代原本的值。
   * - 選擇選項
     - ``WR_element_select_by_value`` / ``_by_index`` / ``_by_visible_text``
     - ``WR_pw_select_option``、``WR_pw_element_select_option``
     - Playwright 收值、``{"index": n}`` 或 ``{"label": text}``。
   * - 等待
     - ``WR_implicitly_wait``
     - ``WR_pw_wait_for_selector`` / ``_url`` / ``_load_state`` /
       ``_timeout``
     - Playwright 在每個動作前還會自動等元素可操作。
   * - 逾時
     - ``WR_set_page_load_timeout``、``WR_set_script_timeout``
     - ``WR_pw_set_default_timeout``、
       ``WR_pw_set_default_navigation_timeout``
     - Selenium 用秒，Playwright 用毫秒。
   * - JavaScript
     - ``WR_execute_script``、``WR_execute_async_script``
     - ``WR_pw_evaluate``
     - ``WR_set_allow_arbitrary_script(False)`` 會同時關閉兩者。
   * - 截圖
     - ``WR_save_screenshot``、``WR_save_full_page_screenshot``、
       ``WR_get_screenshot_as_png``、``WR_get_screenshot_as_base64``
     - ``WR_pw_screenshot``（``full_page``）、``WR_pw_screenshot_bytes``
     - Playwright 沒有 base64 形式。
   * - Cookie
     - ``WR_get_cookies``、``WR_get_cookie``、``WR_add_cookie``、
       ``WR_delete_cookie``、``WR_delete_all_cookies``、``WR_save_cookies``、
       ``WR_load_cookies``
     - ``WR_pw_get_cookies``、``WR_pw_add_cookies``（清單）、
       ``WR_pw_clear_cookies``
     - Playwright 不能依名稱取得或刪除，也不能存成檔案或從檔案載入。
   * - 分頁
     - ``WR_new_window``、``WR_switch``、``WR_switch_to_window_by_url``、
       ``WR_switch_to_window_by_title``、``WR_close_window``
     - ``WR_pw_new_page``、``WR_pw_switch_to_page``、``WR_pw_close_page``、
       ``WR_pw_page_count``
     - Playwright 只能依索引切換。
   * - Frame
     - ``WR_switch``、``WR_iframe_switch_chain``、
       ``WR_iframe_back_to_default``
     - ``WR_pw_frame_locator_chain``
     - Playwright 透過 locator 指定 frame，而不是切進去；之後的 ``WR_pw_*``
       命令仍作用在頁面上。
   * - 裝置模擬
     - ``WR_set_device_metrics`` + ``WR_set_user_agent``
     - ``WR_pw_emulate``、``WR_pw_list_devices``
     - Selenium 的做法只支援 Chromium（CDP），也沒有具名裝置。
   * - 地理位置、時區、語系
     - ``WR_set_geolocation``、``WR_set_timezone``、``WR_set_locale``
     - ``WR_pw_set_geolocation``、``WR_pw_set_timezone``、
       ``WR_pw_set_locale``
     - Selenium 的只支援 Chromium（CDP）。``WR_pw_set_timezone`` 與
       ``WR_pw_set_locale`` 會重建 Playwright context，關掉它的分頁並清掉
       cookie。
   * - 網路節流、原始 CDP
     - ``WR_throttle``、``WR_set_network_conditions``、
       ``WR_execute_cdp_cmd``、``WR_cdp``
     - ``WR_pw_throttle``、``WR_pw_cdp``
     - 兩邊都只支援 Chromium。
   * - Storage、service worker、shadow DOM、上傳、自我修復、axe、效能
     - ``WR_local_storage_*``、``WR_session_storage_*``、``WR_sw_*``、
       ``WR_shadow_query``、``WR_upload_file``、``WR_find_with_healing``、
       ``WR_a11y_run_audit``、``WR_perf_collect``
     - 同名加上 ``WR_pw_`` 前綴（``WR_pw_shadow_query``、
       ``WR_pw_a11y_run_audit`` …）
     - 行為相同。

只有 Selenium 有
----------------

Playwright 做不到：

* Internet Explorer 與真正的 Safari；Playwright 的 WebKit 不是 Safari。
* Selenium Grid 與雲端 grid（``WR_start_remote_driver``、
  ``WR_connect_browserstack`` …）：它們使用 WebDriver 協定，Playwright
  不支援。
* Appium 行動 session（``WR_appium_*``）。
* 視窗位置與大小（``WR_maximize_window``、``WR_minimize_window``、
  ``WR_fullscreen_window``、``WR_set_window_position``、
  ``WR_set_window_rect``）：Playwright 控制的是 viewport，不是作業系統的
  視窗。最接近的是 ``WR_pw_set_viewport_size``。

Playwright 還沒有（Playwright API 本身支援）：

* ``WR_add_script_to_evaluate_on_new_document``、``WR_block_urls`` /
  ``WR_unblock_urls``、``WR_set_cache_disabled``、
  ``WR_clear_geolocation_override``、``WR_bring_to_front``、
  ``WR_print_page``、``WR_set_user_agent``、``WR_set_extra_http_headers``、
  ``WR_set_download_directory`` / ``WR_wait_for_download``、
  ``WR_attach_to_existing_browser``；
* 同時開多個 driver（多次 ``WR_new_driver``、
  ``WR_change_index_of_webdriver``）；
* ``WR_element_submit``、``WR_element_value_of_css_property``、
  ``WR_element_get_dom_attribute``、``WR_check_current_webdriver``、
  ``WR_element_assert``；
* ``WR_scroll``、``WR_scroll_to_top``、``WR_scroll_to_bottom``、
  ``WR_drag_and_drop_offset``；
* 依 URL 或標題切換分頁；callback（callback executor 沒有 ``WR_pw_*``
  命令）；
* 視覺回歸（``WR_visual_capture_baseline``、``WR_visual_compare``）與瀏覽器
  錄製器（``WR_recorder_*``）。

只有 Playwright 有
------------------

Selenium 做不到：

* WebKit。
* trace viewer 與原生錄影。
* 每個動作前自動等元素可操作；Selenium 只有 implicit 與 explicit wait。

Selenium 還沒有：

* ``WR_pw_check``、``WR_pw_uncheck``、``WR_pw_element_is_checked``、
  ``WR_pw_element_inner_text``、``WR_pw_element_inner_html``，以及用原始
  selector 找元素（``WR_pw_find_element``）；
* ``WR_pw_route_mock`` / ``WR_pw_route_mock_json``。Selenium 有 CDP Fetch
  的基本命令（``WR_enable_fetch_interception`` …），但 action 檔永遠拿不到
  被暫停請求的 id，所以無法完成；
* ``WR_pw_start_har_recording``、``WR_pw_event_capture_start``、
  ``WR_pw_assert_no_console_errors``；
* ``WR_pw_grant_permissions``、``WR_pw_clock_install``，以及具名裝置
  （``WR_pw_emulate``）。

兩邊都還沒有
------------

* 在 action 檔裡接受或關閉 JavaScript 對話框。Selenium 可以用 ``WR_switch``
  取得 alert，但沒有接受或關閉的命令；Playwright 會自動關閉對話框，除非在
  對話框出現前已註冊 handler。
* role 與文字 locator（Playwright 的 ``get_by_role`` …）。Selenium 只能用
  XPath 近似。

雲端 Grid
=========

對應 BrowserStack / Sauce Labs / LambdaTest 的 helper。

Appium（行動）
==============

``start_appium_session`` 建立 Appium driver 並掛在 Selenium wrapper 上，既
有 ``WR_*`` 命令直接適用 mobile session。

``appium_integration.gestures`` 提供高階手勢：``swipe`` / ``scroll`` /
``long_press`` / ``pinch`` / ``double_tap``，優先用 ``mobile:`` 擴充
否則退回 W3C Actions。
