"""執行 script / CDP / BiDi listener / Fetch interception。

JavaScript execution, Chrome DevTools Protocol commands, W3C BiDi listeners,
and CDP Fetch interception primitives.
"""
from __future__ import annotations

import base64

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class _ScriptingMixin:
    """提供同步 / 非同步 JS、CDP、BiDi、Fetch 攔截原語。

    Synchronous and asynchronous JavaScript, CDP commands, BiDi listeners,
    and CDP Fetch interception primitives.
    """

    # exec selenium command
    def execute(self, driver_command: str, params: dict | None = None) -> dict | None:
        """
        執行 Selenium WebDriver 的底層命令
        Execute a raw WebDriver command

        :param driver_command: WebDriver 指令名稱 / WebDriver command name
        :param params: 指令參數 / command parameters
        :return: 執行結果 (dict) / execution result as dict
        """
        web_runner_logger.info(f"WebDriverWrapper execute, driver_command: {driver_command}, params: {params}")
        param = locals()
        try:
            record_action_to_list("webdriver wrapper execute", param, None)
            return self.current_webdriver.execute(driver_command, params)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper execute, driver_command: {driver_command}, params: {params}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper execute", param, error)

    def execute_script(self, script: str, *args):
        """
        在當前頁面執行 JavaScript，回傳 JS 的回傳值。
        Execute JavaScript on the current page and return the result.

        :param script: JavaScript 程式碼 / JavaScript code
        :param args: 傳入 JS 的參數 / arguments passed to JS
        :return: JS 回傳值（dict / list / 字面值 / None）
                 The value returned by the script (dict / list / literal / None)
        """
        web_runner_logger.info(f"WebDriverWrapper execute_script, script: {script}")
        param = locals()
        try:
            value = self.current_webdriver.execute_script(script, *args)
            record_action_to_list("webdriver wrapper execute_script", param, None)
            return value
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper execute_script, script: {script}, failed: {error!r}")
            record_action_to_list("webdriver wrapper execute_script", param, error)
            return None

    def execute_cdp_cmd(self, cmd: str, cmd_args: dict | None = None):
        """
        在當前 driver 上執行 Chrome DevTools Protocol 命令 (僅 Chromium 系)。
        Issue a Chrome DevTools Protocol command on the current driver (Chromium-only).

        典型用途：在頁面腳本之前注入 stealth JavaScript，例如
        ``execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js})``。

        Typical use case: inject stealth JavaScript before any page script runs, e.g.
        ``execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js})``.

        :param cmd: CDP 方法名稱，例如 "Page.addScriptToEvaluateOnNewDocument"
                    CDP method name, e.g. "Page.addScriptToEvaluateOnNewDocument"
        :param cmd_args: CDP 參數 dict / CDP params dict
        :return: CDP 回傳 dict / CDP response dict
        """
        # 延遲匯入避免循環依賴 / Lazy import to avoid circular dependency
        from je_web_runner.utils.cdp.cdp_commands import CDPError

        web_runner_logger.info(f"WebDriverWrapper execute_cdp_cmd, cmd: {cmd}")
        param = locals()
        try:
            if self.current_webdriver is None:
                raise CDPError("no Selenium driver active")
            if not hasattr(self.current_webdriver, "execute_cdp_cmd"):
                raise CDPError("active driver does not support CDP (non-Chromium browser?)")
            result = self.current_webdriver.execute_cdp_cmd(cmd, cmd_args or {})
            record_action_to_list("webdriver wrapper execute_cdp_cmd", param, None)
            return result
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper execute_cdp_cmd, cmd: {cmd}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper execute_cdp_cmd", param, error)
            raise

    def add_script_to_evaluate_on_new_document(self, source: str) -> str | None:
        """
        在每次新文件載入前注入一段 JavaScript (常用於 anti-bot / stealth)。
        Inject a JavaScript snippet that will run before any page script on every
        new document. Commonly used for anti-bot / stealth setups.

        包裝 CDP ``Page.addScriptToEvaluateOnNewDocument``。
        Wraps CDP ``Page.addScriptToEvaluateOnNewDocument``.

        :param source: 要注入的 JavaScript 原始碼 / JS source to inject
        :return: CDP 回傳的 script identifier，可用於後續 ``removeScriptToEvaluateOnNewDocument``
                 The script identifier returned by CDP
        """
        result = self.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument", {"source": source}
        )
        if isinstance(result, dict):
            return result.get("identifier")
        return None

    def set_user_agent(self, user_agent: str) -> None:
        """
        以 CDP ``Network.setUserAgentOverride`` 動態覆寫 User-Agent。
        Override User-Agent at runtime via CDP ``Network.setUserAgentOverride``.

        比 ``--user-agent`` 啟動參數彈性，可在 driver 啟動後任意時刻切換。
        More flexible than the ``--user-agent`` launch arg — can be switched after start.
        """
        self.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": user_agent})

    def set_extra_http_headers(self, headers: dict) -> None:
        """
        以 CDP ``Network.setExtraHTTPHeaders`` 為所有後續請求附加 header。
        Attach extra HTTP headers to all subsequent requests via CDP
        ``Network.setExtraHTTPHeaders``.

        :param headers: header 名稱對應到值 (皆為字串) / header name → string value
        """
        self.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": headers})

    def set_geolocation(self, latitude: float, longitude: float, accuracy: float = 100) -> None:
        """
        以 CDP ``Emulation.setGeolocationOverride`` 覆寫地理位置。
        Override geolocation via CDP ``Emulation.setGeolocationOverride``.

        :param latitude: 緯度 / latitude
        :param longitude: 經度 / longitude
        :param accuracy: 精準度 (公尺) / accuracy in meters
        """
        self.execute_cdp_cmd(
            "Emulation.setGeolocationOverride",
            {"latitude": latitude, "longitude": longitude, "accuracy": accuracy},
        )

    def set_timezone(self, timezone_id: str) -> None:
        """
        以 CDP ``Emulation.setTimezoneOverride`` 覆寫時區。
        Override timezone via CDP ``Emulation.setTimezoneOverride``.

        :param timezone_id: IANA 時區字串，例如 ``"Asia/Tokyo"`` / IANA timezone, e.g. ``"Asia/Tokyo"``
        """
        self.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": timezone_id})

    def set_locale(self, locale: str) -> None:
        """
        以 CDP ``Emulation.setLocaleOverride`` 覆寫語系。
        Override locale via CDP ``Emulation.setLocaleOverride``.

        :param locale: BCP47 語系字串，例如 ``"ja-JP"`` / BCP47 locale, e.g. ``"ja-JP"``
        """
        self.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": locale})

    def set_device_metrics(
            self,
            width: int,
            height: int,
            device_scale_factor: float = 1,
            mobile: bool = False,
    ) -> None:
        """
        以 CDP ``Emulation.setDeviceMetricsOverride`` 覆寫裝置外觀 (viewport / DPR / mobile)。
        Override device metrics (viewport / DPR / mobile flag) via CDP
        ``Emulation.setDeviceMetricsOverride``.

        :param width: viewport 寬 / viewport width
        :param height: viewport 高 / viewport height
        :param device_scale_factor: DPR，預設 1 / device pixel ratio
        :param mobile: 是否啟用手機模式 / mobile mode flag
        """
        self.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": device_scale_factor,
                "mobile": mobile,
            },
        )

    def clear_device_metrics(self) -> None:
        """
        清除 ``set_device_metrics`` 設定。
        Clear device metrics override.
        """
        self.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride")

    def clear_geolocation_override(self) -> None:
        """
        清除 ``set_geolocation`` 設定。
        Clear geolocation override.
        """
        self.execute_cdp_cmd("Emulation.clearGeolocationOverride")

    def set_network_conditions(
            self,
            offline: bool = False,
            latency: float = 0,
            download_throughput: float = -1,
            upload_throughput: float = -1,
    ) -> None:
        """
        以 CDP ``Network.emulateNetworkConditions`` 模擬網路條件 (離線、節流)。
        Emulate network conditions via CDP ``Network.emulateNetworkConditions``.

        :param offline: 是否離線 / True for offline
        :param latency: 延遲毫秒數 / latency in ms
        :param download_throughput: 下載速度 bytes/s，``-1`` 表示不限制
                                    download speed in bytes/s; ``-1`` for unlimited
        :param upload_throughput: 上傳速度 bytes/s，``-1`` 表示不限制
                                  upload speed in bytes/s; ``-1`` for unlimited
        """
        self.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": offline,
                "latency": latency,
                "downloadThroughput": download_throughput,
                "uploadThroughput": upload_throughput,
            },
        )

    def block_urls(self, patterns: list[str]) -> None:
        """
        透過 CDP ``Network.setBlockedURLs`` 阻擋符合任一 pattern 的請求。
        Block requests matching any pattern via CDP ``Network.setBlockedURLs``.

        Pattern 支援 ``*`` wildcard，例如 ``"*.doubleclick.net/*"``。
        Patterns support ``*`` wildcards, e.g. ``"*.doubleclick.net/*"``.
        """
        self.execute_cdp_cmd("Network.setBlockedURLs", {"urls": list(patterns)})

    def unblock_urls(self) -> None:
        """
        清空 ``block_urls`` 列表。
        Clear all blocked URL patterns.
        """
        self.execute_cdp_cmd("Network.setBlockedURLs", {"urls": []})

    def set_cache_disabled(self, disabled: bool = True) -> None:
        """
        透過 CDP ``Network.setCacheDisabled`` 切換 HTTP 快取。
        Toggle HTTP cache via CDP ``Network.setCacheDisabled``.
        """
        self.execute_cdp_cmd("Network.setCacheDisabled", {"cacheDisabled": disabled})

    # --- BiDi event listeners (Selenium 4.16+ required) ---
    def _bidi_script(self):
        """取得 ``driver.script`` 服務並驗證可用性 / Resolve driver.script and validate."""
        script = getattr(self.current_webdriver, "script", None)
        if script is None:
            raise WebRunnerException(
                "BiDi unavailable: driver has no 'script' service. "
                "Use set_driver(enable_bidi=True) and Selenium >= 4.16."
            )
        return script

    def add_console_listener(self, callback) -> int | None:
        """
        訂閱瀏覽器 console 訊息事件 (透過 W3C BiDi)。
        Subscribe to browser console message events via W3C BiDi.

        :param callback: 接收單一 ``ConsoleLogEntry`` 參數的可呼叫物
                         Callable taking a single ``ConsoleLogEntry`` argument
        :return: 訂閱 id，用於 ``remove_console_listener`` / subscription id for removal
        """
        web_runner_logger.info("WebDriverWrapper add_console_listener")
        param = locals()
        try:
            subscription_id = self._bidi_script().add_console_message_handler(callback)
            record_action_to_list("webdriver wrapper add_console_listener", param, None)
            return subscription_id
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper add_console_listener failed: {error!r}")
            record_action_to_list("webdriver wrapper add_console_listener", param, error)
            raise

    def add_js_error_listener(self, callback) -> int | None:
        """
        訂閱頁面 JavaScript 例外事件 (透過 W3C BiDi)。
        Subscribe to JavaScript exception events via W3C BiDi.
        """
        web_runner_logger.info("WebDriverWrapper add_js_error_listener")
        param = locals()
        try:
            subscription_id = self._bidi_script().add_javascript_error_handler(callback)
            record_action_to_list("webdriver wrapper add_js_error_listener", param, None)
            return subscription_id
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper add_js_error_listener failed: {error!r}")
            record_action_to_list("webdriver wrapper add_js_error_listener", param, error)
            raise

    def remove_console_listener(self, subscription_id: int) -> bool:
        """
        移除 ``add_console_listener`` 註冊的訂閱。
        Remove a console listener subscription.

        :return: 是否成功移除 / True if removed without error
        """
        web_runner_logger.info(f"WebDriverWrapper remove_console_listener, id: {subscription_id}")
        param = locals()
        try:
            self._bidi_script().remove_console_message_handler(subscription_id)
            record_action_to_list("webdriver wrapper remove_console_listener", param, None)
            return True
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper remove_console_listener failed: {error!r}")
            record_action_to_list("webdriver wrapper remove_console_listener", param, error)
            return False

    def remove_js_error_listener(self, subscription_id: int) -> bool:
        """
        移除 ``add_js_error_listener`` 註冊的訂閱。
        Remove a JS error listener subscription.
        """
        web_runner_logger.info(f"WebDriverWrapper remove_js_error_listener, id: {subscription_id}")
        param = locals()
        try:
            self._bidi_script().remove_javascript_error_handler(subscription_id)
            record_action_to_list("webdriver wrapper remove_js_error_listener", param, None)
            return True
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper remove_js_error_listener failed: {error!r}")
            record_action_to_list("webdriver wrapper remove_js_error_listener", param, error)
            return False

    def set_download_directory(self, download_path: str, behavior: str = "allow") -> None:
        """
        透過 CDP ``Browser.setDownloadBehavior`` 指定下載資料夾 (headless 必備)。
        Set the download directory via CDP ``Browser.setDownloadBehavior``;
        required to receive downloads in headless mode.

        :param download_path: 下載資料夾路徑 / download directory
        :param behavior: ``"allow"`` / ``"deny"`` / ``"default"``，預設 ``"allow"``
                         CDP behavior; defaults to ``"allow"``
        """
        self.execute_cdp_cmd(
            "Browser.setDownloadBehavior",
            {"behavior": behavior, "downloadPath": download_path},
        )

    # --- CDP Fetch interception primitives ---
    # 這些方法只是 Fetch.* CDP 命令的薄包裝；要實際攔截事件 (Fetch.requestPaused)
    # 仍需使用者自行透過 Selenium BiDi 或 trio-based devtools listener 訂閱事件。
    # These methods are thin wrappers around Fetch.* CDP commands. To actually
    # receive Fetch.requestPaused events, the caller must subscribe via
    # Selenium BiDi or trio-based devtools listeners on their own.
    @staticmethod
    def _headers_dict_to_list(headers) -> list:
        """將 ``{name: value}`` dict 轉成 CDP 要求的 ``[{"name":..., "value":...}]``。"""
        if isinstance(headers, dict):
            return [{"name": str(k), "value": str(v)} for k, v in headers.items()]
        return list(headers)

    @staticmethod
    def _normalize_fetch_patterns(patterns) -> list:
        """str → ``{"urlPattern": str}``；dict → 原樣；None → 攔截所有 URL。"""
        if patterns is None:
            return [{"urlPattern": "*"}]
        normalized = []
        for pattern in patterns:
            if isinstance(pattern, str):
                normalized.append({"urlPattern": pattern})
            elif isinstance(pattern, dict):
                normalized.append(pattern)
            else:
                raise WebRunnerException(
                    f"unsupported fetch pattern type: {type(pattern).__name__}"
                )
        return normalized

    def enable_fetch_interception(
            self,
            patterns: list | None = None,
            handle_auth: bool = False,
    ) -> None:
        """
        啟動 CDP ``Fetch.enable`` 開始攔截請求。
        Enable CDP ``Fetch.enable`` to start intercepting requests.

        :param patterns: ``None`` 表示攔截所有；可傳 ``List[str]`` (每個視為 ``urlPattern``)
                         或 ``List[dict]`` (完整 CDP RequestPattern 結構)。
                         ``None`` intercepts everything. Accepts ``List[str]`` (each treated
                         as a ``urlPattern``) or full ``List[RequestPattern dict]``.
        :param handle_auth: 是否同時攔截 401 / 407 auth challenge
                            Whether to also intercept 401 / 407 auth challenges
        """
        self.execute_cdp_cmd(
            "Fetch.enable",
            {
                "patterns": self._normalize_fetch_patterns(patterns),
                "handleAuthRequests": handle_auth,
            },
        )

    def disable_fetch_interception(self) -> None:
        """停止 Fetch 攔截 / Disable Fetch interception."""
        self.execute_cdp_cmd("Fetch.disable")

    def continue_request(
            self,
            request_id: str,
            url: str | None = None,
            method: str | None = None,
            post_data=None,
            headers=None,
    ) -> None:
        """
        放行 (或改寫後放行) 一個被 ``Fetch.requestPaused`` 暫停的請求。
        Continue (optionally modifying) a request paused by ``Fetch.requestPaused``.

        :param request_id: ``Fetch.requestPaused`` 事件提供的 ``requestId``
        :param url: 改寫後的 URL；``None`` 表示維持原本
        :param method: 改寫後的 HTTP method；``None`` 表示維持原本
        :param post_data: ``str`` 或 ``bytes``；會自動 base64 編碼
        :param headers: ``dict`` 或 ``List[{"name", "value"}]``
        """
        params: dict = {"requestId": request_id}
        if url is not None:
            params["url"] = url
        if method is not None:
            params["method"] = method
        if post_data is not None:
            if isinstance(post_data, str):
                post_data = post_data.encode("utf-8")
            params["postData"] = base64.b64encode(post_data).decode("ascii")
        if headers is not None:
            params["headers"] = self._headers_dict_to_list(headers)
        self.execute_cdp_cmd("Fetch.continueRequest", params)

    def fulfill_request(
            self,
            request_id: str,
            response_code: int,
            body=None,
            response_headers=None,
            response_phrase: str | None = None,
    ) -> None:
        """
        以指定 response 回應一個被攔截的請求 (不再送出到原伺服器)。
        Fulfill an intercepted request with a synthetic response (no network call).

        :param request_id: ``Fetch.requestPaused`` 提供的 ``requestId``
        :param response_code: HTTP 狀態碼 / HTTP status code
        :param body: ``str`` 或 ``bytes``；會自動 base64 編碼
        :param response_headers: ``dict`` 或 ``List[{"name", "value"}]``
        :param response_phrase: HTTP reason phrase (例如 ``"OK"``)
        """
        params: dict = {"requestId": request_id, "responseCode": response_code}
        if response_headers is not None:
            params["responseHeaders"] = self._headers_dict_to_list(response_headers)
        if body is not None:
            if isinstance(body, str):
                body = body.encode("utf-8")
            params["body"] = base64.b64encode(body).decode("ascii")
        if response_phrase is not None:
            params["responsePhrase"] = response_phrase
        self.execute_cdp_cmd("Fetch.fulfillRequest", params)

    def fail_request(self, request_id: str, error_reason: str = "Aborted") -> None:
        """
        以指定錯誤理由讓被攔截的請求失敗 (用於阻擋 / 模擬網路錯誤)。
        Fail an intercepted request with the given reason (block / simulate network error).

        :param request_id: ``Fetch.requestPaused`` 提供的 ``requestId``
        :param error_reason: CDP ``ErrorReason`` 列舉，常見值：``"Aborted"`` /
                             ``"AccessDenied"`` / ``"TimedOut"`` / ``"Failed"`` /
                             ``"NameNotResolved"`` / ``"InternetDisconnected"``
        """
        self.execute_cdp_cmd(
            "Fetch.failRequest",
            {"requestId": request_id, "errorReason": error_reason},
        )

    def execute_async_script(self, script: str, *args):
        """
        執行非同步 JavaScript
        Execute asynchronous JavaScript

        :param script: 要執行的 JS 程式碼 / JavaScript code to execute
        :param args: 傳入 JS 的參數 / arguments passed to JS
        :return: JS 執行結果 (非同步回傳) / result of async JS execution
        """
        web_runner_logger.info(f"WebDriverWrapper execute_async_script, script: {script}")
        param = locals()
        try:
            result = self.current_webdriver.execute_async_script(script, *args)
            record_action_to_list("webdriver wrapper execute_async_script", param, None)
            return result
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper execute_async_script, script: {script}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper execute_async_script", param, error)
