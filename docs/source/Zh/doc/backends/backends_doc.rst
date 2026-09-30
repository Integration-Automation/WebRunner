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
   * - 附加、設定檔、遠端
     - ``WR_attach_to_existing_browser``、``WR_chrome_options_with_extension``、
       ``WR_start_remote_driver``
     - ``WR_pw_connect_over_cdp``、``WR_pw_launch_persistent``
       （``extension_paths``）、``WR_pw_connect``\ （Playwright browser server）
     - 附加或 persistent 的 Playwright context 選項固定：會重建 context 的
       設定在那裡會拋出例外。結束附加的瀏覽器只會中斷連線。
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
     - ``WR_pw_screenshot``（``full_page``）、``WR_pw_screenshot_bytes``、
       ``WR_pw_screenshot_base64``
     - 兩邊的形式相同。
   * - PDF
     - ``WR_print_page``
     - ``WR_pw_print_page``
     - Playwright 只能從 headless Chromium 列印。
   * - Cookie
     - ``WR_get_cookies``、``WR_get_cookie``、``WR_add_cookie``、
       ``WR_delete_cookie``、``WR_delete_all_cookies``、``WR_save_cookies``、
       ``WR_load_cookies``
     - ``WR_pw_get_cookies``、``WR_pw_get_cookie``、``WR_pw_add_cookies``
       （清單）、``WR_pw_delete_cookie``、``WR_pw_clear_cookies``、
       ``WR_pw_save_storage_state``（用 context 選項 ``storage_state`` 載回）
     - Playwright 存下的狀態同時包含 cookie 與 localStorage。
   * - Submit、CSS 值、DOM 屬性
     - ``WR_element_submit``、``WR_element_value_of_css_property``、
       ``WR_element_get_dom_attribute``
     - ``WR_pw_element_submit``、``WR_pw_element_value_of_css_property``、
       ``WR_pw_element_get_attribute``
     - Playwright 的 ``get_attribute`` 本來就讀 DOM 屬性。
       ``WR_pw_element_submit`` 用表單的 ``requestSubmit``，所以會觸發 submit
       事件與驗證。
   * - 斷言
     - ``WR_check_current_webdriver``、``WR_element_assert``
     - ``WR_pw_check_current_page``\ （``title``、``url`` / ``current_url``、
       ``viewport_size``、``page_count``）、``WR_pw_element_assert``\ （``tag_name``、
       ``text``、``value``、``visible``、``enabled``、``checked``、``size``、
       ``location``）
     - Playwright 的斷言會拋出例外，不符時該動作就失敗。Selenium 的斷言只把
       不符記進測試紀錄，動作仍算成功。
   * - 分頁
     - ``WR_new_window``、``WR_switch``、``WR_switch_to_window_by_url``、
       ``WR_switch_to_window_by_title``、``WR_close_window``
     - ``WR_pw_new_page``、``WR_pw_switch_to_page``（依索引）、
       ``WR_pw_switch_to_page_by_url``、``WR_pw_switch_to_page_by_title``、
       ``WR_pw_close_page``、``WR_pw_page_count``、``WR_pw_bring_to_front``
     - 兩邊的 URL 與標題都比對大小寫敏感的子字串；Playwright 還會追蹤網站自己
       開的分頁。
   * - 捲動、依偏移拖曳
     - ``WR_scroll``、``WR_scroll_to_top``、``WR_scroll_to_bottom``、
       ``WR_drag_and_drop_offset``
     - ``WR_pw_scroll``、``WR_pw_scroll_to_top``、``WR_pw_scroll_to_bottom``、
       ``WR_pw_drag_and_drop_offset``
     - Playwright 的拖曳收 selector；Selenium 的拖曳傳給它的元素。
   * - Init script、封鎖 URL
     - ``WR_add_script_to_evaluate_on_new_document``、``WR_block_urls`` /
       ``WR_unblock_urls``\ （CDP）
     - ``WR_pw_add_init_script``、``WR_pw_block_urls`` / ``WR_pw_unblock_urls``
     - Selenium 的只支援 Chromium。兩邊的 pattern 都以 ``*`` 代表任意字元。
       Playwright 的兩者都會帶到重建的 context；兩個 init script 命令都受
       任意腳本閘門管制。
   * - Frame
     - ``WR_switch``、``WR_iframe_switch_chain``、
       ``WR_iframe_back_to_default``
     - ``WR_pw_switch_to_frame``\ （一個 selector，或巢狀 iframe 的一串 selector）、
       ``WR_pw_switch_to_parent_frame``、``WR_pw_switch_to_main_frame``
     - 兩邊的模型相同：切換後 selector 命令都作用在選定的 frame，直到切回來；
       Playwright 在導覽或切換分頁時也會回到頁面。滑鼠、鍵盤與截圖一律作用在
       頁面上。
   * - 裝置模擬
     - ``WR_set_device_metrics`` + ``WR_set_user_agent``
     - ``WR_pw_emulate``、``WR_pw_list_devices``
     - Selenium 的做法只支援 Chromium（CDP），也沒有具名裝置。
   * - 地理位置、時區、語系
     - ``WR_set_geolocation``、``WR_set_timezone``、``WR_set_locale``
     - ``WR_pw_set_geolocation``、``WR_pw_set_timezone``、
       ``WR_pw_set_locale``
     - ``WR_pw_clear_geolocation`` 清除覆寫（Selenium：
       ``WR_clear_geolocation_override``）。Selenium 的只支援 Chromium（CDP）。``WR_pw_set_timezone`` 與
       ``WR_pw_set_locale`` 會重建 Playwright context：cookie、localStorage
       與目前分頁的網址會帶過去，其他開著的分頁會關閉。
   * - User agent、額外 header、其他 context 選項
     - ``WR_set_user_agent``、``WR_set_extra_http_headers``\ （CDP）
     - ``WR_pw_set_user_agent``、``WR_pw_set_extra_http_headers``、
       ``WR_pw_set_context_options``（任何 ``browser.new_context`` 選項）、
       帶 ``context_options`` 的 ``WR_pw_launch``
     - Selenium 的只支援 Chromium。Playwright 維持一份合併後的 context
       選項，所以每個設定都不會蓋掉其他設定。
   * - 下載、快取
     - ``WR_set_download_directory`` + ``WR_wait_for_download``、
       ``WR_set_cache_disabled``\ （CDP）
     - ``WR_pw_download(selector, save_to)``\ （點擊並儲存一步完成）、
       ``WR_pw_set_cache_disabled``
     - Playwright 的快取開關各瀏覽器都能用：只要有 route 生效，HTTP 快取就會
       關閉。
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

* 同時開多個 driver（多次 ``WR_new_driver``、
  ``WR_change_index_of_webdriver``）；
* callback（callback executor 沒有 ``WR_pw_*`` 命令）；
* 視覺回歸（``WR_visual_capture_baseline``、``WR_visual_compare``）與瀏覽器
  錄製器（``WR_recorder_*``）。

只有 Playwright 有
------------------

Selenium 做不到：

* WebKit。
* trace viewer 與原生錄影（``WR_pw_tracing_start`` / ``WR_pw_tracing_stop``、
  ``WR_pw_video_start`` / ``WR_pw_video_stop``）。
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
  （``WR_pw_emulate``）；
* 回應 JavaScript 對話框：``WR_pw_set_dialog_policy``\ （``accept``，可附 prompt
  文字；``dismiss``）與 ``WR_pw_last_dialog``。Selenium 可以用 ``WR_switch``
  取得 alert，但沒有接受或關閉的命令。

Selenium 只能近似：以使用者的角度找元素，``WR_pw_find_by``\ （``role``、
``text``、``label``、``placeholder``、``alt_text``、``title``、``test_id``）。
Selenium 只能用 XPath 表達。

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
