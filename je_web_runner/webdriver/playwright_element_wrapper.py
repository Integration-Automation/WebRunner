"""
Playwright 元素操作包裝器，對齊 ``WebElementWrapper`` 的常用 API。
Element-operation wrapper for the Playwright backend, mirroring the public
surface of ``WebElementWrapper`` so existing element-flow scripts have an
analogue.

採用「找完元素先存起來、後續動作對著當前元素操作」的流程，與既有
Selenium 路徑一致；亦支援多元素清單與索引切換。
Follows the same "find-then-operate" flow as the Selenium path: actions run
against the currently captured element, and a list-of-elements form supports
index switching.
"""
from __future__ import annotations

from typing import List, Optional, Union

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class PlaywrightElementError(WebRunnerException):
    """Raised when an element-level Playwright operation cannot proceed."""


def _record(name: str, params, error: Optional[Exception]) -> None:
    record_action_to_list(f"Playwright element {name}", params, error)


class PlaywrightElementWrapper:
    """
    Playwright 元素操作包裝器
    Element-operation wrapper for Playwright handles.
    """

    def __init__(self) -> None:
        self.current_element = None
        self.current_element_list: Optional[List[object]] = None

    def _require_element(self):
        if self.current_element is None:
            raise PlaywrightElementError("no current element; call find_element first")
        return self.current_element

    def click(self) -> None:
        web_runner_logger.info("PlaywrightElementWrapper click")
        try:
            self._require_element().click()
            _record("click", None, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper click failed: {error!r}")
            _record("click", None, error)

    def dblclick(self) -> None:
        web_runner_logger.info("PlaywrightElementWrapper dblclick")
        try:
            self._require_element().dblclick()
            _record("dblclick", None, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper dblclick failed: {error!r}")
            _record("dblclick", None, error)

    def hover(self) -> None:
        web_runner_logger.info("PlaywrightElementWrapper hover")
        try:
            self._require_element().hover()
            _record("hover", None, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper hover failed: {error!r}")
            _record("hover", None, error)

    def fill(self, input_value: str) -> None:
        """Fill (replace) the element's value."""
        web_runner_logger.info(f"PlaywrightElementWrapper fill: {input_value!r}")
        params = {"input_value": input_value}
        try:
            self._require_element().fill(input_value)
            _record("fill", params, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper fill failed: {error!r}")
            _record("fill", params, error)

    def type_text(self, input_value: str, delay: float = 0) -> None:
        """Type text key-by-key (analogue of Selenium ``send_keys``)."""
        web_runner_logger.info(f"PlaywrightElementWrapper type_text: {input_value!r}")
        params = {"input_value": input_value, "delay": delay}
        try:
            self._require_element().type(input_value, delay=delay)
            _record("type_text", params, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper type_text failed: {error!r}")
            _record("type_text", params, error)

    def press(self, key: str) -> None:
        web_runner_logger.info(f"PlaywrightElementWrapper press: {key!r}")
        params = {"key": key}
        try:
            self._require_element().press(key)
            _record("press", params, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper press failed: {error!r}")
            _record("press", params, error)

    def clear(self) -> None:
        """Clear the value (Playwright equivalent of fill('')) ."""
        self.fill("")

    def check(self) -> None:
        web_runner_logger.info("PlaywrightElementWrapper check")
        try:
            self._require_element().check()
            _record("check", None, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper check failed: {error!r}")
            _record("check", None, error)

    def uncheck(self) -> None:
        web_runner_logger.info("PlaywrightElementWrapper uncheck")
        try:
            self._require_element().uncheck()
            _record("uncheck", None, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper uncheck failed: {error!r}")
            _record("uncheck", None, error)

    def select_option(self, value: Union[str, list, dict]) -> List[str]:
        web_runner_logger.info(f"PlaywrightElementWrapper select_option: {value!r}")
        params = {"value": value}
        try:
            result = self._require_element().select_option(value)
            _record("select_option", params, None)
            return result
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper select_option failed: {error!r}")
            _record("select_option", params, error)
            return []

    def get_attribute(self, name: str) -> Optional[str]:
        web_runner_logger.info(f"PlaywrightElementWrapper get_attribute: {name!r}")
        params = {"name": name}
        try:
            value = self._require_element().get_attribute(name)
            _record("get_attribute", params, None)
            return value
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper get_attribute failed: {error!r}")
            _record("get_attribute", params, error)
            return None

    def get_property(self, name: str):
        """Read a JS property via the element handle."""
        web_runner_logger.info(f"PlaywrightElementWrapper get_property: {name!r}")
        params = {"name": name}
        try:
            handle = self._require_element().get_property(name)
            value = handle.json_value() if handle is not None else None
            _record("get_property", params, None)
            return value
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper get_property failed: {error!r}")
            _record("get_property", params, error)
            return None

    def inner_text(self) -> Optional[str]:
        web_runner_logger.info("PlaywrightElementWrapper inner_text")
        try:
            value = self._require_element().inner_text()
            _record("inner_text", None, None)
            return value
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper inner_text failed: {error!r}")
            _record("inner_text", None, error)
            return None

    def inner_html(self) -> Optional[str]:
        web_runner_logger.info("PlaywrightElementWrapper inner_html")
        try:
            value = self._require_element().inner_html()
            _record("inner_html", None, None)
            return value
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper inner_html failed: {error!r}")
            _record("inner_html", None, error)
            return None

    def is_visible(self) -> bool:
        web_runner_logger.info("PlaywrightElementWrapper is_visible")
        try:
            value = self._require_element().is_visible()
            _record("is_visible", None, None)
            return value
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper is_visible failed: {error!r}")
            _record("is_visible", None, error)
            return False

    def is_enabled(self) -> bool:
        web_runner_logger.info("PlaywrightElementWrapper is_enabled")
        try:
            value = self._require_element().is_enabled()
            _record("is_enabled", None, None)
            return value
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper is_enabled failed: {error!r}")
            _record("is_enabled", None, error)
            return False

    def is_checked(self) -> bool:
        web_runner_logger.info("PlaywrightElementWrapper is_checked")
        try:
            value = self._require_element().is_checked()
            _record("is_checked", None, None)
            return value
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper is_checked failed: {error!r}")
            _record("is_checked", None, error)
            return False

    def scroll_into_view(self) -> None:
        web_runner_logger.info("PlaywrightElementWrapper scroll_into_view")
        try:
            self._require_element().scroll_into_view_if_needed()
            _record("scroll_into_view", None, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper scroll_into_view failed: {error!r}")
            _record("scroll_into_view", None, error)

    def screenshot(self, filename: str) -> Optional[str]:
        web_runner_logger.info(f"PlaywrightElementWrapper screenshot: {filename}")
        params = {"filename": filename}
        try:
            target = filename + ".png"
            self._require_element().screenshot(path=target)
            _record("screenshot", params, None)
            return target
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper screenshot failed: {error!r}")
            _record("screenshot", params, error)
            return None

    def change_element(self, element_index: int) -> None:
        """Switch ``current_element`` to ``current_element_list[element_index]``."""
        web_runner_logger.info(f"PlaywrightElementWrapper change_element: {element_index}")
        params = {"element_index": element_index}
        try:
            if not self.current_element_list:
                raise PlaywrightElementError("no element list captured")
            self.current_element = self.current_element_list[element_index]
            _record("change_element", params, None)
        except Exception as error:  # noqa: BLE001
            web_runner_logger.error(f"PlaywrightElementWrapper change_element failed: {error!r}")
            _record("change_element", params, error)


# 全域單例，呼叫 PlaywrightWrapper.find_element_with_test_object_record 時會更新此實例
# Global singleton; PlaywrightWrapper.find_element_with_test_object_record updates it.
playwright_element_wrapper = PlaywrightElementWrapper()
