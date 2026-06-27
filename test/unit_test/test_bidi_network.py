"""BiDi network module tests — assert the real Selenium 4.x BiDi API.

The handlers route through ``network.add_request_handler(event, callback)``;
there is no separate ``add_response_handler`` and ``add_auth_handler`` takes
``(username, password)``, so the wrapper must use ``add_request_handler`` with
the right event name. ``test_event_names_valid_against_real_selenium`` guards
those names against the actual Selenium Network class.
"""
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

    def test_add_request_handler_uses_before_request_event(self):
        network = MagicMock()
        network.add_request_handler.return_value = 11
        driver = self._driver_with_network(network)
        cb = lambda e: None  # noqa: E731
        self.assertEqual(add_request_handler(driver, cb), 11)
        network.add_request_handler.assert_called_once_with("before_request", cb)

    def test_add_response_handler_uses_response_started_event(self):
        network = MagicMock()
        network.add_request_handler.return_value = 22
        driver = self._driver_with_network(network)
        cb = lambda e: None  # noqa: E731
        self.assertEqual(add_response_handler(driver, cb), 22)
        network.add_request_handler.assert_called_once_with("response_started", cb)

    def test_add_auth_handler_uses_auth_required_event(self):
        network = MagicMock()
        network.add_request_handler.return_value = 33
        driver = self._driver_with_network(network)
        cb = lambda e: None  # noqa: E731
        self.assertEqual(add_auth_handler(driver, cb), 33)
        network.add_request_handler.assert_called_once_with("auth_required", cb)

    def test_no_network_attribute_raises(self):
        driver = MagicMock(spec=["execute"])  # no 'network' attribute
        with self.assertRaises(BidiNetworkError):
            add_request_handler(driver, lambda e: None)

    def test_missing_add_request_handler_wrapped(self):
        network = MagicMock(spec=["unrelated_method"])
        driver = self._driver_with_network(network)
        with self.assertRaises(BidiNetworkError):
            add_request_handler(driver, lambda e: None)

    def test_clear_uses_clear_request_handlers(self):
        network = MagicMock()
        network.clear_request_handlers = MagicMock()
        driver = self._driver_with_network(network)
        self.assertTrue(clear_network_handlers(driver))
        network.clear_request_handlers.assert_called_once()

    def test_clear_returns_false_on_exception(self):
        network = MagicMock()
        network.clear_request_handlers = MagicMock(side_effect=RuntimeError("boom"))
        driver = self._driver_with_network(network)
        self.assertFalse(clear_network_handlers(driver))

    def test_clear_without_method_raises(self):
        network = MagicMock(spec=["unrelated"])
        driver = self._driver_with_network(network)
        with self.assertRaises(BidiNetworkError):
            clear_network_handlers(driver)

    def test_event_names_valid_against_real_selenium(self):
        # The events this module passes to add_request_handler must be valid in
        # Selenium's BiDi Network — add_request_handler looks them up in BOTH
        # EVENTS and PHASES, so each must be present in both.
        from selenium.webdriver.common.bidi.network import Network
        for event in ("before_request", "response_started", "auth_required"):
            self.assertIn(event, Network.EVENTS, event)
            self.assertIn(event, Network.PHASES, event)


if __name__ == "__main__":
    unittest.main()
