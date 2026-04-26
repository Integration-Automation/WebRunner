"""
TestObject ↔ Playwright selector 對映工具。
Convert WebRunner ``TestObject`` records into Playwright selector strings.

允許既有以 TestObject 撰寫的腳本直接重用於 Playwright backend。
Lets scripts written against the WebRunner TestObject model run on the
Playwright backend without rewriting locators.
"""
from __future__ import annotations

from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.test_object.test_object_class import TestObject
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import (
    test_object_record,
)


class PlaywrightLocatorError(WebRunnerException):
    """Raised when a TestObject cannot be turned into a valid selector."""


def _normalise(strategy: str) -> str:
    return (strategy or "").strip().upper()


def test_object_to_selector(test_object: TestObject) -> str:
    """
    將 ``TestObject`` 轉成 Playwright 可識別的選擇器
    Translate a ``TestObject`` into a Playwright-flavoured selector.

    :param test_object: WebRunner TestObject 實例
    :return: Playwright selector 字串
    """
    if test_object is None:
        raise PlaywrightLocatorError("test_object is None")
    name = test_object.test_object_name
    strategy = _normalise(test_object.test_object_type)
    if strategy in {"", "CSS_SELECTOR"}:
        return name
    if strategy == "XPATH":
        return f"xpath={name}"
    if strategy == "ID":
        return f"#{name}"
    if strategy == "NAME":
        return f"[name=\"{name}\"]"
    if strategy == "CLASS_NAME":
        return f".{name}"
    if strategy == "TAG_NAME":
        return name
    if strategy == "LINK_TEXT":
        return f"text={name}"
    if strategy == "PARTIAL_LINK_TEXT":
        return f":has-text(\"{name}\")"
    raise PlaywrightLocatorError(f"unsupported locator strategy for Playwright: {strategy!r}")


def selector_for_recorded_name(element_name: str) -> str:
    """
    從 ``test_object_record`` 取出已儲存的 TestObject 並轉成 Playwright selector
    Look up a stored TestObject by name and return its Playwright selector.

    :param element_name: 之前以 ``WR_SaveTestObject`` 註冊的名稱
    :return: Playwright selector 字串
    """
    test_object = test_object_record.test_object_record_dict.get(element_name)
    if test_object is None:
        raise PlaywrightLocatorError(f"no test object recorded under name {element_name!r}")
    return test_object_to_selector(test_object)
