# WebRunner command reference

Auto-generated from the executor's event_dict (403 commands).

| Command | Signature | Summary |
| --- | --- | --- |
| `WR_a11y_load_axe` | `(path: 'str') -> 'str'` | 讀取本地 axe-core JS 原始碼檔案 / Read a local axe-core source file. |
| `WR_a11y_run_audit` | `(axe_source: 'str', options: 'Optional[Dict[str, Any]]' = None) -> 'Dict[str, Any]'` | 在當前 Selenium 頁面執行 axe.run，回傳結果 dict |
| `WR_a11y_summarise` | `(results: 'Dict[str, Any]') -> 'List[Dict[str, Any]]'` | 將 axe 結果壓縮成只含 ``id`` / ``impact`` / ``help`` / ``nodes`` 數量的清單 |
| `WR_add_cookie` | `(cookie_dict: dict) -> None` | 新增 cookie 到當前頁面 |
| `WR_add_package_to_callback_executor` | `(package)` | 將套件的成員加入到 callback_executor 的 event_dict |
| `WR_add_package_to_executor` | `(package)` | 將套件的成員加入到 executor 的 event_dict |
| `WR_appium_android_caps` | `(app: 'str', device_name: 'str' = 'Android Emulator', platform_version: 'str' = '13', automation_name: 'str' = 'UiAutomator2', extra: 'Dict[str, Any]' = None) -> 'Dict[str, Any]'` | Convenience: build a capabilities dict for Android. |
| `WR_appium_ios_caps` | `(app: 'str', device_name: 'str' = 'iPhone 15', platform_version: 'str' = '17', automation_name: 'str' = 'XCUITest', extra: 'Dict[str, Any]' = None) -> 'Dict[str, Any]'` |  |
| `WR_appium_quit` | `() -> 'None'` | Quit whatever driver is currently registered on the WebRunner wrapper. |
| `WR_appium_start` | `(server_url: 'str', capabilities: 'Dict[str, Any]', register: 'bool' = True) -> 'Any'` | 建立 Appium WebDriver 並註冊到 ``webdriver_wrapper_instance`` |
| `WR_assert_no_secrets` | `(data: 'Any') -> 'None'` | 掃描並在有發現時拋例外 / Scan and raise ``SecretsFound`` on any hit. |
| `WR_audit_security_headers` | `(headers: 'Dict[str, str]', required: 'Optional[List[Dict[str, Any]]]' = None) -> 'List[Dict[str, Any]]'` | 對 headers dict 套用規則表，回傳所有違反項目 |
| `WR_audit_security_headers_url` | `(url: 'str', timeout: 'int' = 30, required: 'Optional[List[Dict[str, Any]]]' = None) -> 'List[Dict[str, Any]]'` | GET ``url`` 並稽核回應 headers |
| `WR_back` | `() -> None` | 返回上一頁 / Navigate back |
| `WR_browserstack_capabilities` | `(browser_name: 'str' = 'chrome', browser_version: 'str' = 'latest', os_name: 'str' = 'Windows', os_version: 'str' = '11', project: 'Optional[str]' = None, build: 'Optional[str]' = None, name: 'Optional[str]' = None, extra: 'Optional[Dict[str, Any]]' = None) -> 'Dict[str, Any]'` | Build a W3C-style capability dict for BrowserStack. |
| `WR_build_action_schema` | `() -> 'Dict[str, Any]'` | 產生一份描述 action JSON 結構的 Draft 2020-12 Schema |
| `WR_build_command_reference` | `(title: 'str' = 'WebRunner command reference') -> 'str'` | 產生整份命令參考（Markdown 字串） |
| `WR_build_dependency_graph` | `(paths: 'Sequence[str]') -> 'Dict[str, List[str]]'` | 依基本檔名建立 ``{path: [dep_path, ...]}`` 圖 |
| `WR_build_replay_html` | `(records: 'Optional[List[Dict[str, Any]]]' = None, screenshot_dir: 'Optional[str]' = None, title: 'str' = 'WebRunner replay') -> 'str'` | 產生 self-contained HTML 報告字串 |
| `WR_cdp` | `(method: 'str', params: 'Optional[Dict[str, Any]]' = None) -> 'Any'` | 在當前 Selenium driver 執行 CDP 命令 |
| `WR_change_index_of_webdriver` | `(index_of_webdriver: int) -> None` | 切換當前 WebDriver |
| `WR_check_current_webdriver` | `(check_dict: dict) -> None` | 驗證當前 WebDriver 狀態，若不符合會拋出例外 |
| `WR_chrome_options_with_extension` | `(crx_or_dir: 'str', options: 'Optional[ChromeOptions]' = None) -> 'ChromeOptions'` | 回傳已掛上擴充功能的 ChromeOptions |
| `WR_classify_error` | `(error_repr: 'str') -> 'Optional[str]'` | 依錯誤字串嘗試判定 transient / environment；無法判定回傳 None |
| `WR_classify_failure` | `(error_repr: 'str', ledger_path: 'Optional[str]' = None, file_path: 'Optional[str]' = None) -> 'str'` | 綜合錯誤字串與 ledger 歷史回傳分類 |
| `WR_classify_failures` | `(failures: 'Iterable[Dict[str, Any]]', ledger_path: 'Optional[str]' = None) -> 'Dict[str, str]'` | 對 ``[{function_name, exception, file_path?}, ...]`` 各分類 |
| `WR_CleanTestObject` | `() -> None` | 清空所有測試物件紀錄 |
| `WR_clear_fallback_locators` | `() -> 'None'` |  |
| `WR_clear_test_objects` | `() -> None` | 清空所有測試物件紀錄 |
| `WR_click_element` | `() -> None` | 點擊 WebElement |
| `WR_connect_browserstack` | `(username: 'str', access_key: 'str', capabilities: 'Optional[Dict[str, Any]]' = None, hub_url: 'Optional[str]' = None) -> 'WebDriver'` |  |
| `WR_connect_lambdatest` | `(username: 'str', access_key: 'str', capabilities: 'Optional[Dict[str, Any]]' = None, hub_url: 'Optional[str]' = None) -> 'WebDriver'` |  |
| `WR_connect_saucelabs` | `(username: 'str', access_key: 'str', capabilities: 'Optional[Dict[str, Any]]' = None, hub_url: 'Optional[str]' = None) -> 'WebDriver'` |  |
| `WR_dashboard_start` | `(host: 'str' = '127.0.0.1', port: 'int' = 0) -> 'str'` |  |
| `WR_dashboard_stop` | `() -> 'None'` |  |
| `WR_db_assert_count` | `(connection_url: 'str', sql: 'str', expected: 'int', params: 'Optional[Dict[str, Any]]' = None) -> 'None'` | 斷言 SQL 回傳列數等於 ``expected``。 |
| `WR_db_assert_empty` | `(connection_url: 'str', sql: 'str', params: 'Optional[Dict[str, Any]]' = None) -> 'None'` | 斷言查詢沒有任何結果。 |
| `WR_db_assert_exists` | `(connection_url: 'str', sql: 'str', params: 'Optional[Dict[str, Any]]' = None) -> 'None'` | 斷言查詢回傳至少一列。 |
| `WR_db_assert_value` | `(connection_url: 'str', sql: 'str', column: 'str', expected: 'Any', row_index: 'int' = 0, params: 'Optional[Dict[str, Any]]' = None) -> 'None'` | 斷言指定列、指定欄位的值等於 ``expected``。 |
| `WR_db_query` | `(connection_url: 'str', sql: 'str', params: 'Optional[Dict[str, Any]]' = None) -> 'List[Dict[str, Any]]'` | 對 ``connection_url`` 執行帶 bound params 的 SQL，回傳結果（list of dict） |
| `WR_delete_all_cookies` | `() -> None` | 刪除當前頁面的所有 cookies |
| `WR_delete_cookie` | `(name: str) -> None` | 刪除指定名稱的 cookie |
| `WR_delete_snapshot` | `(name: 'str', snapshot_dir: 'str' = 'snapshots') -> 'bool'` | Remove a snapshot file; returns True if it existed. |
| `WR_diff_ab_records` | `(records_a: 'List[Dict[str, Any]]', records_b: 'List[Dict[str, Any]]') -> 'Dict[str, Any]'` | 比對兩側的 record 序列；回傳每步的差異 |
| `WR_diff_har` | `(left: 'Any', right: 'Any') -> 'Dict[str, List[Dict[str, Any]]]'` | 比對兩份 HAR；回傳 ``{added, removed, changed}`` |
| `WR_diff_har_files` | `(left_path: 'str', right_path: 'str') -> 'Dict[str, List[Dict[str, Any]]]'` | 讀取兩個 HAR 檔並比對 / Read two HAR files from disk and diff them. |
| `WR_drag_and_drop` | `(element_name: str, target_element_name: str) -> None` | 使用 TestObjectRecord 中的元素名稱，拖曳元素到另一個元素上 |
| `WR_drag_and_drop_offset` | `(element_name: str, offset_x: int, offset_y: int) -> None` | 使用 TestObjectRecord 中的元素名稱，拖曳元素到指定偏移位置 |
| `WR_element_assert` | `(check_dict: dict) -> None` | 檢查當前 WebElement 是否符合指定條件 |
| `WR_element_change_web_element` | `(element_index: int) -> None` | 切換當前 WebElement |
| `WR_element_check_current_web_element` | `(check_dict: dict) -> None` | 檢查當前 WebElement 是否符合指定條件 |
| `WR_element_clear` | `() -> None` | 清除當前 WebElement 的內容 |
| `WR_element_click` | `() -> None` | 點擊 WebElement |
| `WR_element_get_attribute` | `(name: str) -> str | None` | 取得 WebElement 的屬性 |
| `WR_element_get_dom_attribute` | `(name: str) -> str | None` | 取得 DOM 屬性 |
| `WR_element_get_property` | `(name: str) -> None | str | bool | selenium.webdriver.remote.webelement.WebElement | dict` | 取得 WebElement 的屬性 |
| `WR_element_get_select` | `() -> selenium.webdriver.support.select.Select | None` | 取得 Select 物件 (用於操作下拉選單) |
| `WR_element_input` | `(input_value: str) -> None` | 輸入文字到 WebElement |
| `WR_element_is_displayed` | `() -> bool | None` | 檢查 WebElement 是否顯示 |
| `WR_element_is_enabled` | `() -> bool | None` | 檢查 WebElement 是否可用 |
| `WR_element_is_selected` | `() -> bool | None` | 檢查 WebElement 是否被選取 |
| `WR_element_screenshot` | `(filename: str) -> bool | None` | 對 WebElement 截圖並存檔 |
| `WR_element_select_by_index` | `(index: int) -> None` | 以索引選取 <select> 選項 |
| `WR_element_select_by_value` | `(value: str) -> None` | 以 value 屬性選取 <select> 選項 |
| `WR_element_select_by_visible_text` | `(text: str) -> None` | 以可見文字選取 <select> 選項 |
| `WR_element_submit` | `() -> None` | 提交當前 WebElement |
| `WR_element_value_of_css_property` | `(property_name: str) -> str | None` | 取得 CSS 屬性值 |
| `WR_execute` | `(driver_command: str, params: dict = None) -> dict | None` | 執行 Selenium WebDriver 的底層命令 |
| `WR_execute_action` | `(action_list: list | dict) -> dict` | 執行一系列動作 |
| `WR_execute_async_script` | `(script: str, *args)` | 執行非同步 JavaScript |
| `WR_execute_files` | `(execute_files_list: list) -> list` | 從檔案載入並執行動作 |
| `WR_execute_script` | `(script: str, *args) -> None` | 在當前頁面執行 JavaScript |
| `WR_expand_env_in_action` | `(data: 'Any') -> 'Any'` | 遞迴展開 ``${ENV.KEY}`` 占位符 |
| `WR_expand_with_row` | `(data: 'Any', row: 'Dict[str, Any]') -> 'Any'` | 遞迴展開 ``${ROW.col}`` 占位符 |
| `WR_explicit_wait` | `(wait_time: int, method: Callable = None, until_type: bool = True)` | Selenium 顯式等待 |
| `WR_explict_wait` | `(wait_time: int, method: Callable = None, until_type: bool = True)` | Selenium 顯式等待 |
| `WR_export_action_schema` | `(path: 'str') -> 'str'` | 將 Schema 寫到 ``path`` 並回傳寫出的路徑 |
| `WR_export_command_reference` | `(path: 'str', title: 'Optional[str]' = None) -> 'str'` | Write the Markdown reference to ``path`` and return the resolved path. |
| `WR_export_replay_studio` | `(output_path: 'str', records: 'Optional[List[Dict[str, Any]]]' = None, screenshot_dir: 'Optional[str]' = None, title: 'str' = 'WebRunner replay') -> 'str'` | Write the studio to ``output_path`` and return the resolved path. |
| `WR_faker` | `(method: 'str', *args: 'Any', **kwargs: 'Any') -> 'Any'` | 任意 faker provider 的通用呼叫器 |
| `WR_faker_address` | `() -> 'str'` |  |
| `WR_faker_credit_card` | `() -> 'str'` |  |
| `WR_faker_email` | `() -> 'str'` |  |
| `WR_faker_first_name` | `() -> 'str'` |  |
| `WR_faker_last_name` | `() -> 'str'` |  |
| `WR_faker_name` | `() -> 'str'` |  |
| `WR_faker_password` | `(length: 'int' = 12) -> 'str'` |  |
| `WR_faker_phone` | `() -> 'str'` |  |
| `WR_faker_seed` | `(seed: 'int') -> 'None'` | Set a deterministic seed for reproducible runs. |
| `WR_faker_text` | `(max_chars: 'Optional[int]' = None) -> 'str'` |  |
| `WR_faker_url` | `() -> 'str'` |  |
| `WR_faker_user_agent` | `() -> 'str'` |  |
| `WR_faker_uuid` | `() -> 'str'` |  |
| `WR_filter_paths` | `(paths: 'Iterable[str]', include: 'Optional[Sequence[str]]' = None, exclude: 'Optional[Sequence[str]]' = None) -> 'List[str]'` | 篩選 action 檔路徑清單 |
| `WR_find_element` | `(element_name: str) -> selenium.webdriver.remote.webelement.WebElement | None` | 使用已儲存的 TestObjectRecord 尋找單一元素 |
| `WR_find_elements` | `(element_name: str) -> list[selenium.webdriver.remote.webelement.WebElement] | None` | 使用已儲存的 TestObjectRecord 尋找多個元素 |
| `WR_find_recorded_element` | `(element_name: str) -> selenium.webdriver.remote.webelement.WebElement | None` | 使用已儲存的 TestObjectRecord 尋找單一元素 |
| `WR_find_recorded_elements` | `(element_name: str) -> list[selenium.webdriver.remote.webelement.WebElement] | None` | 使用已儲存的 TestObjectRecord 尋找多個元素 |
| `WR_find_with_healing` | `(name: 'str')` | 依序嘗試 primary + fallback locator，回傳第一個命中的 WebElement |
| `WR_flakiness_stats` | `(ledger_path: 'str', min_runs: 'int' = 3) -> 'Dict[str, Dict[str, int]]'` | 從 ledger 算出每個檔案的 ``{runs, passes, fails, flaky}`` 統計 |
| `WR_flaky_paths` | `(ledger_path: 'str', min_runs: 'int' = 3, min_fail_rate: 'float' = 0.0) -> 'List[str]'` | 回傳被判為 flaky 的檔案 |
| `WR_forward` | `() -> None` | 前進到下一頁 / Navigate forward |
| `WR_fullscreen_window` | `() -> None` | 全螢幕顯示當前視窗 |
| `WR_generate_all_reports` | `(base_name: 'str', allure_dir: 'Optional[str]' = None, write_manifest: 'bool' = True) -> 'Dict[str, Any]'` | 依預設慣例產出所有報告；回傳 ``{format: [paths produced]}`` 與 manifest 路徑 |
| `WR_generate_allure` | `() -> 'List[Dict[str, Any]]'` | 將目前的 record list 包成單一 Allure test case |
| `WR_generate_allure_report` | `(output_dir: 'str' = 'allure-results') -> 'List[str]'` | 把 test cases 寫成 ``<uuid>-result.json`` |
| `WR_generate_html` | `() -> str` | 產生完整 HTML 報告字串 |
| `WR_generate_html_report` | `(html_name: str = 'default_name')` | 產生並輸出 HTML 報告檔案 |
| `WR_generate_json` | `()` | 產生測試結果的 JSON 結構 |
| `WR_generate_json_report` | `(json_file_name: str = 'default_name')` | 產生並輸出 JSON 測試報告 |
| `WR_generate_junit_xml` | `() -> str` | 產生 JUnit 格式 XML 字串 |
| `WR_generate_junit_xml_report` | `(junit_file_name: str = 'default_name') -> None` | 產生並輸出 JUnit XML 測試報告 |
| `WR_generate_pom_from_html` | `(html: 'str', class_name: 'str') -> 'str'` | Convenience: parse HTML and render the POM class in one call. |
| `WR_generate_pom_from_url` | `(url: 'str', class_name: 'str', timeout: 'int' = 30) -> 'str'` | 從 URL 下載 HTML 並產生 POM 類別 |
| `WR_generate_xml` | `()` | 產生 XML 結構字串 |
| `WR_generate_xml_report` | `(xml_file_name: str = 'default_name')` | 產生並輸出 XML 測試報告 |
| `WR_get_cookie` | `(name: str) -> dict | None` | 取得指定名稱的 cookie |
| `WR_get_cookies` | `() -> list[dict] | None` | 取得當前頁面的所有 cookies |
| `WR_get_env` | `(key: 'str', default: 'Optional[str]' = None) -> 'Optional[str]'` | Return ``os.environ[key]`` with an optional default. |
| `WR_get_log` | `(log_type: str)` | 取得 WebDriver 日誌（``log_type`` 為必填） |
| `WR_get_screenshot_as_base64` | `() -> str | None` | 取得當前頁面截圖 (Base64 字串) |
| `WR_get_screenshot_as_png` | `() -> bytes | None` | 取得當前頁面截圖 (PNG 格式) |
| `WR_get_webdriver_manager` | `(webdriver_name: str, options: List[str] = None, **kwargs) -> None` | 建立新的 WebDriver 實例 |
| `WR_get_window_position` | `(window_handle='current') -> dict | None` | 取得視窗位置 |
| `WR_get_window_rect` | `() -> dict | None` | 取得視窗矩形資訊 (位置與大小) |
| `WR_gh_emit_failures` | `(stream: 'Optional[IO[str]]' = None, file: 'Optional[str]' = None) -> 'List[str]'` | 對 ``test_record_instance`` 內每個失敗紀錄輸出一行 annotation |
| `WR_gh_emit_from_junit_xml` | `(junit_path: 'str', stream: 'Optional[IO[str]]' = None) -> 'List[str]'` | 讀取 JUnit XML 並對其中每個 ``<failure>`` 輸出一行 annotation |
| `WR_gh_format_error` | `(message: 'str', file: 'Optional[str]' = None, line: 'Optional[int]' = None, col: 'Optional[int]' = None, title: 'Optional[str]' = None) -> 'str'` | 產出 ``::error file=...::message`` 行 |
| `WR_http_assert_json_contains` | `(key: 'str', expected: 'Any') -> 'None'` | 斷言上一次 JSON 回應於 ``key`` 的值等於 ``expected`` |
| `WR_http_assert_status` | `(expected: 'int') -> 'None'` | 斷言上一次回應的 HTTP 狀態碼 |
| `WR_http_delete` | `(url: 'str', **kwargs: 'Any') -> 'Dict[str, Any]'` |  |
| `WR_http_get` | `(url: 'str', **kwargs: 'Any') -> 'Dict[str, Any]'` |  |
| `WR_http_patch` | `(url: 'str', **kwargs: 'Any') -> 'Dict[str, Any]'` |  |
| `WR_http_post` | `(url: 'str', **kwargs: 'Any') -> 'Dict[str, Any]'` |  |
| `WR_http_put` | `(url: 'str', **kwargs: 'Any') -> 'Dict[str, Any]'` |  |
| `WR_http_request` | `(method: 'str', url: 'str', timeout: 'int' = 30, headers: 'Optional[Dict[str, str]]' = None, params: 'Optional[Dict[str, Any]]' = None, json_body: 'Any' = None, data: 'Any' = None, **request_kwargs: 'Any') -> 'Dict[str, Any]'` | 通用 HTTP 請求；其他 ``http_*`` 命令皆呼叫此函式 |
| `WR_iframe_back_to_default` | `() -> 'None'` | Return Selenium focus to the top-level frame. |
| `WR_iframe_switch_chain` | `(selectors: 'Sequence[str]') -> 'None'` | 依序切換進入多層 iframe（每層用 CSS selector 指定） |
| `WR_implicitly_wait` | `(time_to_wait: int) -> None` | 設定 Selenium 的隱式等待時間 |
| `WR_indexed_db_drop` | `(db_name: 'str') -> 'None'` | Drop an IndexedDB database by name. Best-effort (Promise resolution skipped). |
| `WR_input_to_element` | `(input_value: str) -> None` | 輸入文字到 WebElement |
| `WR_jira_create_failure_issues` | `(base_url: 'str', email: 'str', api_token: 'str', project_key: 'str', issue_type: 'str' = 'Bug', build_url: 'Optional[str]' = None) -> 'List[Dict[str, Any]]'` | 對 ``test_record_instance`` 內每個失敗紀錄建立一個 issue |
| `WR_jira_create_issue` | `(base_url: 'str', email: 'str', api_token: 'str', project_key: 'str', summary: 'str', description: 'str' = '', issue_type: 'str' = 'Bug', extra_fields: 'Optional[Dict[str, Any]]' = None, timeout: 'int' = 30) -> 'Dict[str, Any]'` | 建立 JIRA issue |
| `WR_lambdatest_capabilities` | `(browser_name: 'str' = 'Chrome', browser_version: 'str' = 'latest', platform_name: 'str' = 'Windows 11', build: 'Optional[str]' = None, name: 'Optional[str]' = None, extra: 'Optional[Dict[str, Any]]' = None) -> 'Dict[str, Any]'` |  |
| `WR_ledger_clear` | `(ledger_path: 'str') -> 'None'` | Delete the ledger file (no-op if missing). |
| `WR_ledger_failed_files` | `(ledger_path: 'str') -> 'List[str]'` | Return paths whose most recent run was a failure. |
| `WR_ledger_passed_files` | `(ledger_path: 'str') -> 'List[str]'` | Return paths whose most recent run was a pass. |
| `WR_ledger_record_run` | `(ledger_path: 'str', file_path: 'str', passed: 'bool') -> 'None'` | Append one run record to the ledger. |
| `WR_left_click` | `(element_name: str = None) -> None` | 使用 TestObject 名稱找到元素並左鍵點擊 |
| `WR_left_click_and_hold` | `(element_name: str = None) -> None` | 使用 TestObject 名稱找到元素並左鍵按住 |
| `WR_left_double_click` | `(element_name: str = None) -> None` | 使用 TestObject 名稱找到元素並左鍵雙擊 |
| `WR_lighthouse_assert_scores` | `(result: 'Dict[str, Any]', thresholds: 'Dict[str, float]') -> 'None'` | 斷言所有指定分數皆達門檻 |
| `WR_lighthouse_run` | `(url: 'str', output_path: 'Optional[str]' = None, lighthouse_path: 'str' = 'lighthouse', chrome_flags: 'Optional[List[str]]' = None, extra_args: 'Optional[List[str]]' = None, timeout: 'int' = 180) -> 'Dict[str, Any]'` | 執行 Lighthouse 並回傳 ``{scores, report_path, raw}`` |
| `WR_lint_action` | `(data: 'Any') -> 'List[Dict[str, Any]]'` | Walk an action structure and return the findings list. |
| `WR_lint_action_file` | `(path: 'str') -> 'List[Dict[str, Any]]'` | Read ``path`` (UTF-8 JSON) and lint the contents. |
| `WR_lint_severity_counts` | `(findings: 'List[Dict[str, Any]]') -> 'Dict[str, int]'` | Aggregate ``{warning: N, info: M}`` for reporting. |
| `WR_list_commands` | `() -> 'List[str]'` | Just the command names (handy for shell completion). |
| `WR_list_new_downloads` | `(directory: 'str', before: 'List[str]') -> 'List[str]'` | 回傳 ``directory`` 內目前存在但不在 ``before`` 清單中的檔案 |
| `WR_llm_generate_actions` | `(request: 'str', context: 'Optional[str]' = None) -> 'List[Any]'` | 把自然語言敘述轉成 WR_* action JSON 草稿 |
| `WR_llm_has_callable` | `() -> 'bool'` |  |
| `WR_llm_self_heal_locator` | `(name: 'str', html_provider: 'Callable[[], str]') -> 'Dict[str, str]'` | 當既有 fallback locator 都失敗時，呼叫 LLM 提供新的選擇器 |
| `WR_llm_set_callable` | `(callable_obj: 'Optional[Callable[[str], str]]') -> 'None'` | 登錄一個 ``Callable[[str], str]`` 用於後續所有 prompt。 |
| `WR_llm_suggest_locator` | `(html: 'str', description: 'str') -> 'Dict[str, str]'` | 讓 LLM 從 HTML 推斷一個合理的 locator |
| `WR_load_dataset_csv` | `(path: 'str', encoding: 'str' = 'utf-8') -> 'List[Dict[str, str]]'` | 讀取 CSV 為 list of dict（首列為欄位名） |
| `WR_load_dataset_json` | `(path: 'str', encoding: 'str' = 'utf-8') -> 'List[Dict[str, Any]]'` | 讀取 JSON 為 list of dict |
| `WR_load_env` | `(env_name: 'Optional[str]' = None, env_dir: 'str' = '.', override: 'bool' = False) -> 'str'` | 載入指定環境的 ``.env`` 檔 |
| `WR_local_storage_all` | `() -> 'dict'` |  |
| `WR_local_storage_clear` | `() -> 'None'` |  |
| `WR_local_storage_get` | `(key: 'str') -> 'Optional[str]'` |  |
| `WR_local_storage_remove` | `(key: 'str') -> 'None'` |  |
| `WR_local_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_locust_build_user_class` | `(actions: 'List[Dict[str, Any]]', wait_min: 'float' = 1.0, wait_max: 'float' = 3.0) -> 'type'` | 依 actions 動態建立一個 ``HttpUser`` 子類別 |
| `WR_locust_run` | `(host: 'str', actions: 'List[Dict[str, Any]]', num_users: 'int' = 10, spawn_rate: 'float' = 2.0, run_seconds: 'float' = 60.0, wait_min: 'float' = 1.0, wait_max: 'float' = 3.0) -> 'Dict[str, Any]'` | 無頭模式跑 Locust 並回傳統計 |
| `WR_match_snapshot` | `(name: 'str', value: 'str', snapshot_dir: 'str' = 'snapshots') -> 'str'` | 比對快照；首次執行會建立基準。 |
| `WR_maximize_window` | `() -> None` | 最大化當前視窗 |
| `WR_migrate_action` | `(data: 'Any') -> 'Tuple[Any, List[Dict[str, Any]]]'` | 將 action 結構內所有舊命令名改寫為新名 |
| `WR_migrate_action_file` | `(path: 'str', dry_run: 'bool' = True) -> 'Dict[str, Any]'` | Read ``path``, rewrite legacy names, optionally write back when |
| `WR_migrate_directory` | `(directory: 'str', dry_run: 'bool' = True) -> 'List[Dict[str, Any]]'` | 遍歷目錄內所有 ``.json`` 檔做遷移 |
| `WR_minimize_window` | `() -> None` | 最小化當前視窗 |
| `WR_move_by_offset` | `(offset_x: int, offset_y: int) -> None` | 滑鼠移動指定偏移量 |
| `WR_move_to_element` | `(element_name: str)` | 使用 TestObjectRecord 中的元素名稱，將滑鼠移動到指定元素 |
| `WR_move_to_element_with_offset` | `(element_name: str, offset_x: int, offset_y: int) -> None` | 使用 TestObjectRecord 中的元素名稱，將滑鼠移動到指定元素並加上偏移量 |
| `WR_new_driver` | `(webdriver_name: str, options: List[str] = None, **kwargs) -> None` | 建立新的 WebDriver 實例 |
| `WR_notify_run_summary` | `(webhook_url: 'str', header: 'str' = 'WebRunner Run Summary') -> 'int'` | 一鍵：取摘要 → Slack 格式 → 送出 |
| `WR_notify_slack` | `(webhook_url: 'str', summary: 'Optional[Dict[str, Any]]' = None, header: 'str' = 'WebRunner Run Summary') -> 'int'` | 將摘要包成 Slack incoming-webhook 格式並送出 |
| `WR_notify_webhook` | `(url: 'str', payload: 'Dict[str, Any]', timeout: 'int' = 10, headers: 'Optional[Dict[str, str]]' = None) -> 'int'` | POST 任意 JSON payload 到 webhook，回傳 HTTP 狀態碼 |
| `WR_oauth_bearer_header` | `(access_token: 'str') -> 'Dict[str, str]'` | Convenience: build the Authorization header for HTTP commands. |
| `WR_oauth_clear_cache` | `() -> 'None'` |  |
| `WR_oauth_client_credentials` | `(token_url: 'str', client_id: 'str', client_secret: 'str', scope: 'Optional[str]' = None, cache_key: 'Optional[str]' = None, timeout: 'int' = 30) -> 'Dict[str, Any]'` | OAuth2 client-credentials 流程 |
| `WR_oauth_get_cached` | `(cache_key: 'str') -> 'Optional[Dict[str, Any]]'` |  |
| `WR_oauth_password_grant` | `(token_url: 'str', client_id: 'str', client_secret: 'str', username: 'str', password: 'str', scope: 'Optional[str]' = None, cache_key: 'Optional[str]' = None, timeout: 'int' = 30) -> 'Dict[str, Any]'` | OAuth2 password grant（多數 IdP 已棄用，僅 legacy 系統用） |
| `WR_oauth_refresh_token` | `(token_url: 'str', client_id: 'str', client_secret: 'str', refresh_token: 'str', cache_key: 'Optional[str]' = None, timeout: 'int' = 30) -> 'Dict[str, Any]'` |  |
| `WR_order_factory` | `(default_currency: 'str' = 'USD') -> 'Factory'` |  |
| `WR_parse_shard_spec` | `(spec: 'str') -> 'Tuple[int, int]'` | 把 ``"1/4"`` 解析為 ``(1, 4)`` |
| `WR_partition` | `(paths: 'Sequence[str]', index: 'int', total: 'int') -> 'List[str]'` | 回傳該 shard 應該執行的檔案路徑（依檔名 SHA-1 對 ``total`` 取模） |
| `WR_partition_with_spec` | `(paths: 'Sequence[str]', spec: 'str') -> 'List[str]'` | Convenience: parse the spec then partition. |
| `WR_pause` | `(seconds: int) -> None` | 暫停指定秒數 (注意：可能導致 Selenium 拋出例外) |
| `WR_perf_assert_within` | `(metrics: 'Dict[str, Any]', thresholds: 'Dict[str, float]') -> 'None'` | 斷言所有指標都不超過上限 |
| `WR_perf_collect` | `(observe_ms: 'int' = 1000) -> 'Dict[str, Any]'` | 透過 ``execute_async_script`` 抓取效能指標 |
| `WR_perform` | `() -> None` | 執行累積的 ActionChains 動作 |
| `WR_press_key` | `(keycode_on_key_class, element_name: str = None) -> None` | 使用 TestObject 名稱找到元素並按下鍵盤按鍵 |
| `WR_product_factory` | `() -> 'Factory'` |  |
| `WR_pw_a11y_run_audit` | `(axe_source: 'str', options: 'Optional[Dict[str, Any]]' = None) -> 'Dict[str, Any]'` | 在當前 Playwright 頁面執行 axe.run，回傳結果 dict |
| `WR_pw_add_cookies` | `(cookies: 'List[dict]') -> 'None'` |  |
| `WR_pw_assert_no_4xx_or_5xx` | `() -> 'None'` |  |
| `WR_pw_assert_no_5xx` | `() -> 'None'` |  |
| `WR_pw_assert_no_console_errors` | `() -> 'None'` |  |
| `WR_pw_back` | `() -> 'None'` |  |
| `WR_pw_cdp` | `(method: 'str', params: 'Optional[Dict[str, Any]]' = None) -> 'Any'` | 在當前 Playwright page 執行 CDP 命令 |
| `WR_pw_cdp_reset_sessions` | `() -> 'None'` | Drop cached Playwright CDP sessions (e.g. after browser restart). |
| `WR_pw_check` | `(selector: 'str') -> 'None'` |  |
| `WR_pw_clear_cookies` | `() -> 'None'` |  |
| `WR_pw_clear_permissions` | `() -> 'None'` |  |
| `WR_pw_click` | `(selector: 'str') -> 'None'` |  |
| `WR_pw_clock_install` | `(fake_now_ms: 'Optional[float]' = None) -> 'None'` |  |
| `WR_pw_clock_run_for` | `(duration_ms: 'float') -> 'None'` |  |
| `WR_pw_clock_set_time` | `(time_ms: 'float') -> 'None'` |  |
| `WR_pw_close_page` | `(index: 'Optional[int]' = None) -> 'None'` |  |
| `WR_pw_console_messages` | `() -> 'List[Dict[str, Any]]'` |  |
| `WR_pw_content` | `() -> 'str'` |  |
| `WR_pw_dblclick` | `(selector: 'str') -> 'None'` |  |
| `WR_pw_drag_and_drop` | `(source_selector: 'str', target_selector: 'str') -> 'None'` |  |
| `WR_pw_element_change` | `(element_index: 'int') -> 'None'` | Switch ``current_element`` to ``current_element_list[element_index]``. |
| `WR_pw_element_check` | `() -> 'None'` |  |
| `WR_pw_element_clear` | `() -> 'None'` | Clear the value (Playwright equivalent of fill('')) . |
| `WR_pw_element_click` | `() -> 'None'` |  |
| `WR_pw_element_dblclick` | `() -> 'None'` |  |
| `WR_pw_element_fill` | `(input_value: 'str') -> 'None'` | Fill (replace) the element's value. |
| `WR_pw_element_get_attribute` | `(name: 'str') -> 'Optional[str]'` |  |
| `WR_pw_element_get_property` | `(name: 'str')` | Read a JS property via the element handle. |
| `WR_pw_element_hover` | `() -> 'None'` |  |
| `WR_pw_element_inner_html` | `() -> 'Optional[str]'` |  |
| `WR_pw_element_inner_text` | `() -> 'Optional[str]'` |  |
| `WR_pw_element_is_checked` | `() -> 'bool'` |  |
| `WR_pw_element_is_enabled` | `() -> 'bool'` |  |
| `WR_pw_element_is_visible` | `() -> 'bool'` |  |
| `WR_pw_element_press` | `(key: 'str') -> 'None'` |  |
| `WR_pw_element_screenshot` | `(filename: 'str') -> 'Optional[str]'` |  |
| `WR_pw_element_scroll_into_view` | `() -> 'None'` |  |
| `WR_pw_element_select_option` | `(value: 'Union[str, list, dict]') -> 'List[str]'` |  |
| `WR_pw_element_type_text` | `(input_value: 'str', delay: 'float' = 0) -> 'None'` | Type text key-by-key (analogue of Selenium ``send_keys``). |
| `WR_pw_element_uncheck` | `() -> 'None'` |  |
| `WR_pw_emulate` | `(device_name: 'str') -> 'None'` |  |
| `WR_pw_evaluate` | `(expression: 'str', arg: 'Any' = None)` |  |
| `WR_pw_event_capture_clear` | `() -> 'None'` |  |
| `WR_pw_event_capture_start` | `() -> 'None'` | Attach the singleton EventCapture to the active Playwright page. |
| `WR_pw_event_capture_stop` | `() -> 'None'` |  |
| `WR_pw_extension_args` | `(extension_dir: 'str') -> 'List[str]'` | 回傳給 ``pw_launch(args=...)`` 用的旗標清單（Chromium only） |
| `WR_pw_fill` | `(selector: 'str', value: 'str') -> 'None'` |  |
| `WR_pw_find_element` | `(selector: 'str')` |  |
| `WR_pw_find_element_with_test_object_record` | `(element_name: 'str')` |  |
| `WR_pw_find_elements` | `(selector: 'str') -> 'List[Any]'` |  |
| `WR_pw_find_elements_with_test_object_record` | `(element_name: 'str')` |  |
| `WR_pw_find_with_healing` | `(name: 'str')` | Playwright 版自我修復定位 |
| `WR_pw_forward` | `() -> 'None'` |  |
| `WR_pw_frame_locator_chain` | `(selectors: 'Sequence[str]') -> 'Any'` | 依序連結 ``page.frame_locator(selector)`` 形成深層 frame locator |
| `WR_pw_get_cookies` | `() -> 'List[dict]'` |  |
| `WR_pw_grant_permissions` | `(permissions: 'List[str]', origin: 'Optional[str]' = None) -> 'None'` |  |
| `WR_pw_hover` | `(selector: 'str') -> 'None'` |  |
| `WR_pw_indexed_db_drop` | `(db_name: 'str') -> 'None'` |  |
| `WR_pw_keyboard_down` | `(key: 'str') -> 'None'` |  |
| `WR_pw_keyboard_press` | `(key: 'str') -> 'None'` |  |
| `WR_pw_keyboard_type` | `(text: 'str', delay: 'float' = 0) -> 'None'` |  |
| `WR_pw_keyboard_up` | `(key: 'str') -> 'None'` |  |
| `WR_pw_launch` | `(browser: 'str' = 'chromium', headless: 'bool' = True, **options: 'Any') -> 'None'` |  |
| `WR_pw_list_devices` | `() -> 'List[str]'` |  |
| `WR_pw_local_storage_all` | `() -> 'dict'` |  |
| `WR_pw_local_storage_clear` | `() -> 'None'` |  |
| `WR_pw_local_storage_get` | `(key: 'str') -> 'Optional[str]'` |  |
| `WR_pw_local_storage_remove` | `(key: 'str') -> 'None'` |  |
| `WR_pw_local_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_pw_mouse_click` | `(x: 'float', y: 'float', button: 'str' = 'left', click_count: 'int' = 1) -> 'None'` |  |
| `WR_pw_mouse_down` | `(button: 'str' = 'left', click_count: 'int' = 1) -> 'None'` |  |
| `WR_pw_mouse_move` | `(x: 'float', y: 'float', steps: 'int' = 1) -> 'None'` |  |
| `WR_pw_mouse_up` | `(button: 'str' = 'left', click_count: 'int' = 1) -> 'None'` |  |
| `WR_pw_network_responses` | `() -> 'List[Dict[str, Any]]'` |  |
| `WR_pw_new_page` | `() -> 'int'` |  |
| `WR_pw_page_count` | `() -> 'int'` |  |
| `WR_pw_perf_collect` | `(observe_ms: 'int' = 1000) -> 'Dict[str, Any]'` | 透過 ``page.evaluate`` 抓取效能指標 |
| `WR_pw_press` | `(selector: 'str', key: 'str') -> 'None'` |  |
| `WR_pw_quit` | `() -> 'None'` |  |
| `WR_pw_refresh` | `() -> 'None'` |  |
| `WR_pw_route_clear` | `() -> 'None'` |  |
| `WR_pw_route_mock` | `(url_pattern: 'str', response: 'dict') -> 'None'` |  |
| `WR_pw_route_mock_json` | `(url_pattern: 'str', json_data: 'Any', status: 'int' = 200) -> 'None'` |  |
| `WR_pw_route_unmock` | `(url_pattern: 'str') -> 'None'` |  |
| `WR_pw_save_test_object_to_selector` | `(test_object_name: 'str', object_type: 'str' = 'CSS_SELECTOR') -> 'str'` | 把 TestObject 存進 ``test_object_record`` 並回傳對應的 Playwright selector |
| `WR_pw_screenshot` | `(path: 'str', full_page: 'bool' = False) -> 'str'` |  |
| `WR_pw_screenshot_bytes` | `(full_page: 'bool' = False) -> 'bytes'` |  |
| `WR_pw_select_option` | `(selector: 'str', value: 'Any') -> 'List[str]'` |  |
| `WR_pw_session_storage_clear` | `() -> 'None'` |  |
| `WR_pw_session_storage_get` | `(key: 'str') -> 'Optional[str]'` |  |
| `WR_pw_session_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_pw_set_default_navigation_timeout` | `(timeout_ms: 'float') -> 'None'` |  |
| `WR_pw_set_default_timeout` | `(timeout_ms: 'float') -> 'None'` |  |
| `WR_pw_set_geolocation` | `(latitude: 'float', longitude: 'float', accuracy: 'Optional[float]' = None) -> 'None'` |  |
| `WR_pw_set_locale` | `(locale: 'str', accept_language: 'Optional[str]' = None) -> 'None'` |  |
| `WR_pw_set_timezone` | `(timezone_id: 'str') -> 'None'` |  |
| `WR_pw_set_viewport_size` | `(width: 'int', height: 'int') -> 'None'` |  |
| `WR_pw_shadow_query` | `(host_chain: 'Sequence[str]', inner_selector: 'str')` | Resolve the pierce selector against the active Playwright page. |
| `WR_pw_shadow_selector` | `(host_chain: 'Sequence[str]', inner_selector: 'str') -> 'str'` | 把 host 鏈與內層 selector 組成 Playwright ``>>>`` (pierce) 選擇器 |
| `WR_pw_start_har_recording` | `(har_path: 'str', content: 'str' = 'omit') -> 'None'` |  |
| `WR_pw_stop_emulate` | `() -> 'None'` |  |
| `WR_pw_stop_har_recording` | `() -> 'None'` |  |
| `WR_pw_sw_bypass` | `(bypass: 'bool' = True) -> 'None'` | Bypass the service worker via CDP on the active Playwright page. |
| `WR_pw_sw_clear_caches` | `() -> 'List[str]'` |  |
| `WR_pw_sw_unregister` | `() -> 'List[bool]'` |  |
| `WR_pw_switch_to_page` | `(index: 'int') -> 'None'` |  |
| `WR_pw_throttle` | `(preset: 'str') -> 'Any'` | Apply ``preset`` via the active Playwright page's CDP session. |
| `WR_pw_throttle_clear` | `() -> 'Any'` |  |
| `WR_pw_title` | `() -> 'str'` |  |
| `WR_pw_to_url` | `(url: 'str') -> 'None'` |  |
| `WR_pw_type_text` | `(selector: 'str', value: 'str', delay: 'float' = 0) -> 'None'` |  |
| `WR_pw_uncheck` | `(selector: 'str') -> 'None'` |  |
| `WR_pw_upload_file` | `(input_selector: 'str', file_path: 'str') -> 'None'` | 對指定的 file input 送入檔案（Playwright） |
| `WR_pw_url` | `() -> 'str'` |  |
| `WR_pw_viewport_size` | `() -> 'Optional[dict]'` |  |
| `WR_pw_wait_for_load_state` | `(state: 'str' = 'load', timeout: 'Optional[float]' = None) -> 'None'` |  |
| `WR_pw_wait_for_selector` | `(selector: 'str', timeout: 'Optional[float]' = None, state: 'str' = 'visible')` |  |
| `WR_pw_wait_for_timeout` | `(timeout_ms: 'float') -> 'None'` |  |
| `WR_pw_wait_for_url` | `(url: 'str', timeout: 'Optional[float]' = None) -> 'None'` |  |
| `WR_quit` | `() -> None` | 關閉並退出所有 WebDriver |
| `WR_quit_all` | `() -> None` | 關閉並退出所有 WebDriver |
| `WR_quit_current` | `() -> None` | 關閉並退出 WebDriver |
| `WR_read_depends_on` | `(path: 'str') -> 'List[str]'` | 讀取單一檔案的 ``meta.depends_on`` 清單（以 basename 表示）。 |
| `WR_read_metadata` | `(path: 'str') -> 'Dict[str, Any]'` | 讀取 action 檔的 ``meta`` 區塊；若檔案不是 dict 或沒有 meta，回傳空 dict |
| `WR_recorder_pull_events` | `()` |  |
| `WR_recorder_save` | `(output_path, raw_events_path=None)` |  |
| `WR_recorder_start` | `()` |  |
| `WR_recorder_stop` | `()` |  |
| `WR_refresh` | `() -> None` | 重新整理頁面 / Refresh current page |
| `WR_register_fallback_locator` | `(name: 'str', strategy: 'str', value: 'str') -> 'None'` | Public helper for use as a WR_* command. |
| `WR_register_fallback_locators` | `(name: 'str', fallbacks: 'List[Any]') -> 'None'` | Public helper for use as a WR_* command. |
| `WR_release` | `(element_name: str = None) -> None` | 使用 TestObject 名稱找到元素並釋放滑鼠 |
| `WR_release_key` | `(keycode_on_key_class, element_name: str = None) -> None` | 使用 TestObject 名稱找到元素並釋放鍵盤按鍵 |
| `WR_report_expected_paths` | `(base_name: 'str', allure_dir: 'Optional[str]' = None) -> 'Dict[str, List[str]]'` | 回傳每個格式預期寫出的路徑（實際是否存在由 manifest 確認） |
| `WR_reset_actions` | `() -> None` | 清除目前累積的 ActionChains 動作（搭配 ``WR_perform`` 使用） |
| `WR_reset_scheduler` | `() -> 'None'` | Drop all registered jobs and counts (mainly for tests). |
| `WR_right_click` | `(element_name: str = None) -> None` | 使用 TestObject 名稱找到元素並右鍵點擊 |
| `WR_run_ab` | `(action_data: 'Any', setup_a: 'Optional[Callable[[], Any]]' = None, setup_b: 'Optional[Callable[[], Any]]' = None, runner: 'Optional[Callable[[Any], Any]]' = None) -> 'Dict[str, Any]'` | 對兩個環境跑同一份 action 並回傳比對結果 |
| `WR_run_for_users` | `(action_data: 'Any', user_setups: 'List[Tuple[str, Optional[Callable[[], Any]]]]', runner: 'Optional[Callable[[Any], Any]]' = None) -> 'Dict[str, Any]'` | 對每位使用者執行一次 ``action_data``，回傳記錄與差異 |
| `WR_run_scheduler_for` | `(seconds: 'float') -> 'None'` |  |
| `WR_run_scheduler_forever` | `() -> 'None'` |  |
| `WR_run_with_dataset` | `(action_data, rows)` |  |
| `WR_saucelabs_capabilities` | `(browser_name: 'str' = 'chrome', browser_version: 'str' = 'latest', platform_name: 'str' = 'Windows 11', build: 'Optional[str]' = None, name: 'Optional[str]' = None, extra: 'Optional[Dict[str, Any]]' = None) -> 'Dict[str, Any]'` |  |
| `WR_save_test_object` | `(test_object_name: str, object_type: str = None, **kwargs) -> None` | 儲存新的測試物件 |
| `WR_SaveTestObject` | `(test_object_name: str, object_type: str = None, **kwargs) -> None` | 儲存新的測試物件 |
| `WR_scan_secrets` | `(data: 'Any') -> 'List[Dict[str, Any]]'` | 掃描 action 結構，回傳所有疑似秘密的位置 |
| `WR_scan_secrets_file` | `(path: 'str') -> 'List[Dict[str, Any]]'` | 讀取 action JSON 檔並掃描 / Load an action JSON file and scan it. |
| `WR_schedule` | `(name: 'str', interval_seconds: 'float', callback: 'Callable[[], Any]') -> 'None'` |  |
| `WR_scheduler_counts` | `() -> 'Dict[str, int]'` |  |
| `WR_scroll` | `(scroll_x: int, scroll_y: int) -> None` | 滾動頁面 |
| `WR_send_keys` | `(keys_to_send) -> None` | 發送鍵盤按鍵 (按下並釋放) |
| `WR_send_keys_to_element` | `(element_name: str, keys_to_send) -> None` | 使用 TestObject 名稱找到元素並發送鍵盤按鍵 |
| `WR_session_storage_clear` | `() -> 'None'` |  |
| `WR_session_storage_get` | `(key: 'str') -> 'Optional[str]'` |  |
| `WR_session_storage_set` | `(key: 'str', value: 'str') -> 'None'` |  |
| `WR_set_action_span_factory` | `(factory: Callable[[str], Any] | None) -> None` | 登錄一個 context-manager factory，每個 action 會被它包起來 |
| `WR_set_allow_arbitrary_script` | `(enabled: bool) -> None` | 切換是否允許 ``WR_execute_script`` / ``WR_pw_evaluate`` / CDP 命令 |
| `WR_set_driver` | `(webdriver_name: str, webdriver_manager_option_dict: dict = None, options: List[str] = None, **kwargs) -> selenium.webdriver.chrome.webdriver.WebDriver | selenium.webdriver.firefox.webdriver.WebDriver | selenium.webdriver.edge.webdriver.WebDriver | selenium.webdriver.ie.webdriver.WebDriver | selenium.webdriver.safari.webdriver.WebDriver` | 啟動一個新的 WebDriver |
| `WR_set_failure_screenshot_dir` | `(path: str | None) -> None` | 設定 (或停用) 動作失敗時的自動截圖目錄 |
| `WR_set_page_load_timeout` | `(time_to_wait: int) -> None` | 設定頁面載入最大等待時間 / Set max page load wait time |
| `WR_set_record_enable` | `(set_enable: bool = True)` | 開啟或關閉紀錄功能 |
| `WR_set_retry_policy` | `(retries: int = 0, backoff: float = 0.0) -> None` | 設定全域重試策略 |
| `WR_set_script_timeout` | `(time_to_wait: int) -> None` | 設定 script 最大執行時間 / Set max script execution time |
| `WR_set_webdriver_options_capability` | `(key_and_vale_dict: dict) -> selenium.webdriver.ie.options.Options | None` | 設定 WebDriver 的 capabilities |
| `WR_set_window_position` | `(x: int, y: int, window_handle: str = 'current') -> dict | None` | 設定視窗位置 |
| `WR_set_window_rect` | `(x: int = None, y: int = None, width: int = None, height: int = None) -> dict | None` | 設定視窗矩形 (位置與大小)，僅支援 W3C 相容瀏覽器 |
| `WR_set_window_size` | `(width: int, height: int, window_handle: str = 'current') -> None` | 設定視窗大小 |
| `WR_shadow_query` | `(host_chain: 'Sequence[str]', inner_selector: 'str') -> 'Any'` | 在巢狀 Shadow DOM 中查詢 |
| `WR_single_quit` | `() -> None` | 關閉並退出 WebDriver |
| `WR_skip_dependents_of_failed` | `(graph: 'Dict[str, List[str]]', failed: 'Iterable[str]') -> 'List[str]'` | 回傳因為上游失敗而應該跳過的檔案 |
| `WR_snapshot_directory` | `(directory: 'str') -> 'List[str]'` | Take a snapshot of resolved file paths under ``directory``. |
| `WR_start_remote_driver` | `(hub_url: 'str', capabilities: 'Dict[str, Any]', register: 'bool' = True) -> 'WebDriver'` | 啟動 Remote WebDriver；預設將其註冊到 ``webdriver_wrapper_instance`` |
| `WR_stop_scheduler` | `() -> 'None'` |  |
| `WR_summarise_run` | `() -> 'Dict[str, Any]'` | 從 ``test_record_instance`` 產生 pass/fail 統計 |
| `WR_sw_bypass` | `(bypass: 'bool' = True) -> 'None'` | 透過 CDP 設定 ServiceWorker bypass（僅 Chromium 系） |
| `WR_sw_clear_caches` | `() -> 'List[str]'` | 清空 Cache Storage |
| `WR_sw_unregister` | `() -> 'List[bool]'` | 解除註冊當前頁面所有 Service Worker |
| `WR_switch` | `(switch_type: str, switch_target_name: str = None)` | 切換 WebDriver 的上下文 (frame, window, alert...) |
| `WR_tc_cleanup_all` | `() -> 'None'` | Stop every container started by this module. |
| `WR_tc_generic` | `(image: 'str', ports: 'Optional[Dict[int, int]]' = None) -> 'Any'` | 啟動任意 Docker image |
| `WR_tc_postgres` | `(image: 'str' = 'postgres:16-alpine', user: 'str' = 'test', password: 'str' = 'test', dbname: 'str' = 'test') -> 'Any'` | 啟動暫存 Postgres，回傳 container 實例（含 ``get_connection_url()``） |
| `WR_tc_redis` | `(image: 'str' = 'redis:7-alpine') -> 'Any'` |  |
| `WR_tc_started_count` | `() -> 'int'` | How many containers are tracked as live by this module. |
| `WR_tc_stop` | `(container: 'Any') -> 'None'` | Stop a single container started by this module. |
| `WR_testrail_close_run` | `(base_url: 'str', username: 'str', api_key: 'str', run_id: 'int', timeout: 'int' = 30) -> 'Dict[str, Any]'` | 關閉指定的 TestRail run |
| `WR_testrail_results_from_pairs` | `(pairs: 'Iterable[Dict[str, Any]]', comment_field: 'str' = 'comment') -> 'List[Dict[str, Any]]'` | 把 ``[{case_id, passed, comment?}]`` 轉成 TestRail status_id 格式 |
| `WR_testrail_send_results` | `(base_url: 'str', username: 'str', api_key: 'str', run_id: 'int', results: 'List[Dict[str, Any]]', timeout: 'int' = 30) -> 'Dict[str, Any]'` | 將結果送到 ``add_results_for_cases/{run_id}`` |
| `WR_throttle` | `(preset: 'str') -> 'Any'` | Apply ``preset`` via the active Selenium driver's CDP channel. |
| `WR_throttle_clear` | `() -> 'Any'` | Convenience for the ``no_throttling`` preset. |
| `WR_throttle_presets` | `() -> 'list'` | Return all registered preset names. |
| `WR_to_url` | `(url: str) -> None` | 導航到指定 URL |
| `WR_topological_order` | `(graph: 'Dict[str, List[str]]') -> 'List[str]'` | Kahn 演算法拓樸排序；偵測環時拋例外 |
| `WR_update_snapshot` | `(name: 'str', value: 'str', snapshot_dir: 'str' = 'snapshots') -> 'str'` | 強制覆蓋基準 |
| `WR_upload_file` | `(input_selector: 'str', file_path: 'str') -> 'None'` | 對 ``<input type="file">`` 送入檔案路徑（Selenium） |
| `WR_user_factory` | `(prefix: 'str' = 'user') -> 'Factory'` | Default user shape: id / name / email / password. |
| `WR_validate_action_file` | `(json_file_path: 'str') -> 'bool'` | 讀取並驗證動作 JSON 檔案 |
| `WR_validate_action_json` | `(data: 'Union[list, dict]') -> 'bool'` | 驗證動作 JSON 是否符合執行器格式 |
| `WR_visual_capture_baseline` | `(baseline_path: 'str') -> 'str'` | 擷取當前頁面並儲存為基準圖 |
| `WR_visual_compare` | `(baseline_path: 'str', diff_path: 'Optional[str]' = None, current_path: 'Optional[str]' = None, threshold: 'int' = 0) -> 'dict'` | 擷取目前頁面並與基準圖比較 |
| `WR_wait_for_download` | `(directory: 'str', timeout: 'float' = 60.0, suffix: 'Optional[str]' = None, poll_seconds: 'float' = 0.5) -> 'str'` | 等待 ``directory`` 內出現新檔案（會跳過 ``.crdownload`` / ``.part``） |
| `WR_write_pom_to_file` | `(source: 'str', output_path: 'str') -> 'str'` | Write generated source to ``output_path``; returns the path written. |
