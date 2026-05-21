"""BiDi network 模組的 mock-based 測試。"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.bidi.network import (
    BidiNetworkError,
    add_auth_handler,
    add_request_handler,
    add_response_handler,
    clear_network_handlers,
)


class TestBidiNetwork(unittest.TestCase):

    def _driver_with_network(self, network=None):
        driver = MagicMock(spec=["network"])
        driver.network = network if network is not None else MagicMock()
        return driver

    def test_add_request_handler_returns_id(self):
        network = MagicMock()
        network.add_request_handler.return_value = 11
        driver = self._driver_with_network(network)
        cb = lambda e: None  # noqa: E731
        self.assertEqual(add_request_handler(driver, cb), 11)
        network.add_request_handler.assert_called_once_with(cb)

    def test_add_response_handler_returns_id(self):
        network = MagicMock()
        network.add_response_handler.return_value = 22
        driver = self._driver_with_network(network)
        self.assertEqual(add_response_handler(driver, lambda e: None), 22)

    def test_add_auth_handler_returns_id(self):
        network = MagicMock()
        network.add_auth_handler.return_value = 33
        driver = self._driver_with_network(network)
        self.assertEqual(add_auth_handler(driver, lambda e: None), 33)

    def test_no_network_attribute_raises(self):
        driver = MagicMock(spec=["execute"])  # 沒有 network 屬性
        with self.assertRaises(BidiNetworkError):
            add_request_handler(driver, lambda e: None)

    def test_missing_method_wrapped(self):
        # network 存在但缺方法 (例如 Selenium 4.16-4.22)
        network = MagicMock(spec=["unrelated_method"])
        driver = self._driver_with_network(network)
        with self.assertRaises(BidiNetworkError):
            add_request_handler(driver, lambda e: None)

    def test_clear_uses_clear_handlers_if_available(self):
        network = MagicMock()
        network.clear_handlers = MagicMock()
        driver = self._driver_with_network(network)
        self.assertTrue(clear_network_handlers(driver))
        network.clear_handlers.assert_called_once()

    def test_clear_falls_back_to_clear_method(self):
        network = MagicMock(spec=["clear"])
        network.clear = MagicMock()
        driver = self._driver_with_network(network)
        self.assertTrue(clear_network_handlers(driver))
        network.clear.assert_called_once()

    def test_clear_returns_false_on_exception(self):
        network = MagicMock()
        network.clear_handlers = MagicMock(side_effect=RuntimeError("boom"))
        driver = self._driver_with_network(network)
        self.assertFalse(clear_network_handlers(driver))

    def test_clear_without_method_raises(self):
        # 兩個方法都沒有
        network = MagicMock(spec=["unrelated"])
        driver = self._driver_with_network(network)
        with self.assertRaises(BidiNetworkError):
            clear_network_handlers(driver)


if __name__ == "__main__":
    unittest.main()
