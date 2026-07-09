"""Cookies / origin-storage 相關方法 / Cookie and origin storage methods."""
from __future__ import annotations

import json

from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class _CookieMixin:
    """Cookie 操作與 session 持久化 / Cookie operations and session persistence."""

    def get_cookies(self) -> list[dict] | None:
        """
        取得當前頁面的所有 cookies
        Get all cookies from the current page

        :return: cookies 清單，每個 cookie 是 dict
                 list of cookies, each cookie is a dict
        """
        web_runner_logger.info("WebDriverWrapper get_cookies")
        try:
            record_action_to_list("webdriver wrapper get_cookies", None, None)
            return self.current_webdriver.get_cookies()
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_cookies, failed: {error!r}")
            record_action_to_list("webdriver wrapper get_cookies", None, error)

    def get_cookie(self, name: str) -> dict | None:
        """
        取得指定名稱的 cookie
        Get a cookie by name

        :param name: cookie 名稱 / cookie name
        :return: cookie dict
        """
        web_runner_logger.info(f"WebDriverWrapper get_cookie, name: {name}")
        param = locals()
        try:
            record_action_to_list("webdriver wrapper get_cookie", param, None)
            return self.current_webdriver.get_cookie(name)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper get_cookie, name: {name}, failed: {error!r}")
            record_action_to_list("webdriver wrapper get_cookie", param, error)

    def add_cookie(self, cookie_dict: dict) -> None:
        """
        新增 cookie 到當前頁面
        Add a cookie to the current page

        :param cookie_dict: cookie dict，例如 {"name": "session", "value": "12345"}
        """
        web_runner_logger.info(f"WebDriverWrapper add_cookie, cookie_dict: {cookie_dict}")
        param = locals()
        try:
            self.current_webdriver.add_cookie(cookie_dict)
            record_action_to_list("webdriver wrapper add_cookie", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper add_cookie, cookie_dict: {cookie_dict}, failed: {error!r}"
            )
            record_action_to_list("webdriver wrapper add_cookie", param, error)

    def delete_cookie(self, name: str) -> None:
        """
        刪除指定名稱的 cookie
        Delete a cookie by name

        :param name: cookie 名稱 / cookie name
        """
        web_runner_logger.info(f"WebDriverWrapper delete_cookie, name: {name}")
        param = locals()
        try:
            self.current_webdriver.delete_cookie(name)
            record_action_to_list("webdriver wrapper delete_cookie", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper delete_cookie, name: {name}, failed: {error!r}")
            record_action_to_list("webdriver wrapper delete_cookie", param, error)

    def delete_all_cookies(self) -> None:
        """
        刪除當前頁面的所有 cookies
        Delete all cookies from the current page
        """
        web_runner_logger.info("WebDriverWrapper delete_all_cookies")
        try:
            self.current_webdriver.delete_all_cookies()
            record_action_to_list("webdriver wrapper delete_all_cookies", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper delete_all_cookies, failed: {error!r}")
            record_action_to_list("webdriver wrapper delete_all_cookies", None, error)

    def save_cookies(self, file_path: str) -> bool:
        """
        將當前頁面的 cookies 序列化為 JSON 並寫入檔案 (用於 session reuse)。
        Serialize current-page cookies to JSON and write to file (for session reuse).

        注意 / Note: 僅儲存當前頁面 domain 的 cookies；若要跨 domain，需先導航或改用
        ``execute_cdp_cmd("Network.getAllCookies")``。
        Only stores cookies for the current page domain; for cross-domain dumps,
        navigate first or use ``execute_cdp_cmd("Network.getAllCookies")``.

        :param file_path: 目標 JSON 檔案路徑 / target JSON path
        :return: 是否成功 / True if saved
        """
        web_runner_logger.info(f"WebDriverWrapper save_cookies, file_path: {file_path}")
        param = locals()
        try:
            cookies = self.current_webdriver.get_cookies() or []
            with open(file_path, "w", encoding="utf-8") as fh:
                json.dump(cookies, fh, ensure_ascii=False, indent=2)
            record_action_to_list("webdriver wrapper save_cookies", param, None)
            return True
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper save_cookies failed: {error!r}")
            record_action_to_list("webdriver wrapper save_cookies", param, error)
            return False

    def load_cookies(self, file_path: str) -> int:
        """
        從 JSON 檔讀回 cookies 並逐筆套用 (恢復先前的登入態)。
        Load cookies from a JSON file and add them one by one (restore login state).

        注意 / Note: 必須先 ``to_url`` 到對應 domain，否則 ``add_cookie`` 會拋出。
        Must navigate (``to_url``) to a matching domain first; ``add_cookie`` raises otherwise.

        :param file_path: 來源 JSON 檔案路徑 / source JSON path
        :return: 成功套用的 cookie 數量；失敗 (例如 domain 不符) 會略過該筆
                 Number of cookies successfully added; mismatches are skipped
        """
        web_runner_logger.info(f"WebDriverWrapper load_cookies, file_path: {file_path}")
        param = locals()
        try:
            with open(file_path, encoding="utf-8") as fh:
                cookies = json.load(fh)
            added = 0
            for cookie in cookies:
                try:
                    self.current_webdriver.add_cookie(cookie)
                    added += 1
                except Exception as add_error:
                    web_runner_logger.warning(
                        f"WebDriverWrapper load_cookies skipped cookie "
                        f"{cookie.get('name')!r}: {add_error!r}"
                    )
            record_action_to_list("webdriver wrapper load_cookies", param, None)
            return added
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper load_cookies failed: {error!r}")
            record_action_to_list("webdriver wrapper load_cookies", param, error)
            return 0

    def clear_origin_storage(self, origin: str) -> None:
        """
        透過 CDP ``Storage.clearDataForOrigin`` 一次清掉指定 origin 的所有儲存
        (cookies + localStorage + IndexedDB + cache + service workers...)。
        Clear every storage type for an origin via CDP ``Storage.clearDataForOrigin``
        (cookies + localStorage + IndexedDB + cache + service workers + ...).

        :param origin: 完整 origin，例如 ``"https://example.com"``
                       Full origin, e.g. ``"https://example.com"``
        """
        self.execute_cdp_cmd(
            "Storage.clearDataForOrigin",
            {
                "origin": origin,
                "storageTypes": "all",
            },
        )
