"""Selenium ActionChains 包裝 / Selenium ActionChains wrappers."""
from __future__ import annotations

from selenium.webdriver.remote.webelement import WebElement

from je_web_runner.element.web_element_wrapper import web_element_wrapper
from je_web_runner.utils.exception.exceptions import WebRunnerException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_object.test_object_record.test_object_record_class import test_object_record
from je_web_runner.utils.test_record.test_record_class import record_action_to_list


class _ActionsMixin:
    """所有 ActionChains-based 滑鼠 / 鍵盤 / 拖曳動作。

    All ActionChains-based mouse, keyboard, and drag-and-drop operations.
    依賴 ``self._action_chain`` (由主類別在 ``__init__`` / ``set_driver`` 設定)。
    Depends on ``self._action_chain`` set by the host class.
    """

    def move_to_element(self, target_element: WebElement) -> None:
        """
        將滑鼠移動到指定元素
        Move mouse to target web element

        :param target_element: 目標 WebElement / target web element
        """
        web_runner_logger.info(f"WebDriverWrapper move_to_element, target_element: {target_element}")
        param = locals()
        try:
            self._action_chain.move_to_element(target_element)
            record_action_to_list("webdriver wrapper move_to_element", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper move_to_element, target_element: {target_element}, failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper move_to_element", param, error)

    def move_to_element_with_test_object(self, element_name: str):
        """
        使用 TestObjectRecord 中的元素名稱，將滑鼠移動到指定元素
        Move mouse to target element using TestObjectRecord

        :param element_name: 測試物件名稱 / test object name
        """
        web_runner_logger.info(f"WebDriverWrapper move_to_element_with_test_object, element_name: {element_name}")
        param = locals()
        try:
            record = test_object_record.test_object_record_dict.get(element_name)
            if record is None:
                raise WebRunnerException(f"TestObject '{element_name}' not found")
            element = self.current_webdriver.find_element(record.test_object_type, record.test_object_name)
            self._action_chain.move_to_element(element)
            record_action_to_list("webdriver wrapper move_to_element_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper move_to_element_with_test_object, element_name: {element_name}, failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper move_to_element_with_test_object", param, error)

    def move_to_element_with_offset(self, target_element: WebElement, offset_x: int, offset_y: int) -> None:
        """
        將滑鼠移動到指定元素，並加上偏移量
        Move mouse to target element with offset

        :param target_element: 目標 WebElement / target web element
        :param offset_x: X 軸偏移量 / offset on X axis
        :param offset_y: Y 軸偏移量 / offset on Y axis
        """
        web_runner_logger.info(
            f"WebDriverWrapper move_to_element_with_offset, target_element: {target_element}, "
            f"offset_x: {offset_x}, offset_y: {offset_y}"
        )
        param = locals()
        try:
            self._action_chain.move_to_element_with_offset(target_element, offset_x, offset_y)
            record_action_to_list("webdriver wrapper move_to_element_with_offset", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper move_to_element_with_offset failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper move_to_element_with_offset", param, error)

    def move_to_element_with_offset_and_test_object(self, element_name: str, offset_x: int, offset_y: int) -> None:
        """
        使用 TestObjectRecord 中的元素名稱，將滑鼠移動到指定元素並加上偏移量
        Move mouse to target element with offset using TestObjectRecord

        :param element_name: 測試物件名稱 / test object name
        :param offset_x: X 軸偏移量 / offset on X axis
        :param offset_y: Y 軸偏移量 / offset on Y axis
        """
        web_runner_logger.info(
            f"WebDriverWrapper move_to_element_with_offset_and_test_object, element_name: {element_name}, "
            f"offset_x: {offset_x}, offset_y: {offset_y}"
        )
        param = locals()
        try:
            record = test_object_record.test_object_record_dict.get(element_name)
            if record is None:
                raise WebRunnerException(f"TestObject '{element_name}' not found")
            element = self.current_webdriver.find_element(record.test_object_type, record.test_object_name)
            self._action_chain.move_to_element_with_offset(element, offset_x, offset_y)
            record_action_to_list("webdriver wrapper move_to_element_with_offset_and_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper move_to_element_with_offset_and_test_object failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper move_to_element_with_offset_and_test_object", param, error)

    def drag_and_drop(self, web_element: WebElement, target_element: WebElement) -> None:
        """
        拖曳元素到另一個元素上並釋放
        Drag a web element to another target element and drop

        :param web_element: 要拖曳的元素 / element to drag
        :param target_element: 目標元素 / target element to drop onto
        """
        web_runner_logger.info(
            f"WebDriverWrapper drag_and_drop, web_element: {web_element}, target_element: {target_element}"
        )
        param = locals()
        try:
            self._action_chain.drag_and_drop(web_element, target_element)
            record_action_to_list("webdriver wrapper drag_and_drop", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper drag_and_drop failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper drag_and_drop", param, error)

    def drag_and_drop_with_test_object(self, element_name: str, target_element_name: str) -> None:
        """
        使用 TestObjectRecord 中的元素名稱，拖曳元素到另一個元素上
        Drag a web element to another target element using TestObjectRecord

        :param element_name: 要拖曳的元素名稱 / name of element to drag
        :param target_element_name: 目標元素名稱 / name of target element
        """
        web_runner_logger.info(
            f"WebDriverWrapper drag_and_drop_with_test_object, element_name: {element_name}, "
            f"target_element_name: {target_element_name}"
        )
        param = locals()
        try:
            element_record = test_object_record.test_object_record_dict.get(element_name)
            target_record = test_object_record.test_object_record_dict.get(target_element_name)
            if element_record is None or target_record is None:
                raise WebRunnerException(f"TestObject not found: {element_name} or {target_element_name}")

            element = self.current_webdriver.find_element(element_record.test_object_type,
                                                          element_record.test_object_name)
            another_element = self.current_webdriver.find_element(target_record.test_object_type,
                                                                  target_record.test_object_name)

            self._action_chain.drag_and_drop(element, another_element)
            record_action_to_list("webdriver wrapper drag_and_drop_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper drag_and_drop_with_test_object failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper drag_and_drop_with_test_object", param, error)

    def drag_and_drop_offset(self, web_element: WebElement, target_x: int, target_y: int) -> None:
        """
        拖曳元素到指定偏移位置
        Drag a web element to a position with offset

        :param web_element: 要拖曳的元素 / element to drag
        :param target_x: X 軸偏移量 / offset on X axis
        :param target_y: Y 軸偏移量 / offset on Y axis
        """
        web_runner_logger.info(
            f"WebDriverWrapper drag_and_drop_offset, web_element: {web_element}, "
            f"target_x: {target_x}, target_y: {target_y}"
        )
        param = locals()
        try:
            self._action_chain.drag_and_drop_by_offset(web_element, target_x, target_y)
            record_action_to_list("webdriver wrapper drag_and_drop_offset", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper drag_and_drop_offset failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper drag_and_drop_offset", param, error)

    def drag_and_drop_offset_with_test_object(self, element_name: str, offset_x: int, offset_y: int) -> None:
        """
        使用 TestObjectRecord 中的元素名稱，拖曳元素到指定偏移位置
        Drag a web element with offset using TestObjectRecord

        :param element_name: 測試物件名稱 / test object name
        :param offset_x: X 軸偏移量 / offset on X axis
        :param offset_y: Y 軸偏移量 / offset on Y axis
        """
        web_runner_logger.info(
            f"WebDriverWrapper drag_and_drop_offset_with_test_object, element_name: {element_name}, "
            f"offset_x: {offset_x}, offset_y: {offset_y}"
        )
        param = locals()
        try:
            record = test_object_record.test_object_record_dict.get(element_name)
            if record is None:
                raise WebRunnerException(f"TestObject not found: {element_name}")

            element = self.current_webdriver.find_element(record.test_object_type, record.test_object_name)
            self._action_chain.drag_and_drop_by_offset(element, offset_x, offset_y)
            record_action_to_list("webdriver wrapper drag_and_drop_offset_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(
                f"WebDriverWrapper drag_and_drop_offset_with_test_object failed: {repr(error)}"
            )
            record_action_to_list("webdriver wrapper drag_and_drop_offset_with_test_object", param, error)

    def perform(self) -> None:
        """
        執行累積的 ActionChains 動作
        Perform all queued ActionChains actions.

        Selenium 的 ActionChains 是「先排隊、後一次執行」模型。
        ``WR_left_click_and_hold`` / ``WR_move_to_element`` /
        ``WR_release`` / ``WR_press_key`` 等命令只是把動作排入佇列，
        必須最後呼叫 ``WR_perform`` 才會真的觸發；中途要清除請用
        ``WR_reset_actions``。對單純點擊或輸入請改用
        ``WR_element_click`` / ``WR_element_input`` 直接執行，免用
        ActionChains。

        Selenium ActionChains is a queue-then-execute model. Commands like
        ``WR_left_click_and_hold`` / ``WR_move_to_element`` /
        ``WR_release`` / ``WR_press_key`` only enqueue the action; you must
        call ``WR_perform`` at the end to actually fire them, and
        ``WR_reset_actions`` to drop the queue mid-flow. For simple clicks
        or text input prefer ``WR_element_click`` / ``WR_element_input``,
        which run synchronously.
        """
        web_runner_logger.info("WebDriverWrapper perform")
        try:
            self._action_chain.perform()
            record_action_to_list("webdriver wrapper perform", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper perform failed: {repr(error)}")
            record_action_to_list("webdriver wrapper perform", None, error)

    def reset_actions(self) -> None:
        """
        清除目前累積的 ActionChains 動作（搭配 ``WR_perform`` 使用）
        Clear all queued ActionChains actions.

        Use this together with ``WR_perform`` when you want to abort an
        ActionChains sequence partway through. See ``perform`` above for
        the queue-then-execute model.
        """
        web_runner_logger.info("WebDriverWrapper reset_actions")
        try:
            self._action_chain.reset_actions()
            record_action_to_list("webdriver wrapper reset_actions", None, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper reset_actions failed: {repr(error)}")
            record_action_to_list("webdriver wrapper reset_actions", None, error)

    def left_click(self, on_element: WebElement = None) -> None:
        """
        滑鼠左鍵點擊 (可指定元素或當前位置)
        Left click mouse at current position or on a given element

        :param on_element: WebElement 或 None
        """
        web_runner_logger.info(f"WebDriverWrapper left_click, on_element: {on_element}")
        param = locals()
        try:
            self._action_chain.click(on_element)
            record_action_to_list("webdriver wrapper left_click", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper left_click failed: {repr(error)}")
            record_action_to_list("webdriver wrapper left_click", param, error)

    def left_click_with_test_object(self, element_name: str = None) -> None:
        """
        使用 TestObject 名稱找到元素並左鍵點擊
        Left click using a TestObject name

        :param element_name: 測試物件名稱 / test object name
        """
        web_runner_logger.info(f"WebDriverWrapper left_click_with_test_object, element_name: {element_name}")
        param = locals()
        try:
            if element_name is None:
                self._action_chain.click(None)
            else:
                record = test_object_record.test_object_record_dict.get(element_name)
                if record is None:
                    raise WebRunnerException(f"TestObject '{element_name}' not found")
                element = self.current_webdriver.find_element(record.test_object_type, record.test_object_name)
                self._action_chain.click(element)
            record_action_to_list("webdriver wrapper left_click_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper left_click_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper left_click_with_test_object", param, error)

    def left_click_and_hold(self, on_element: WebElement = None) -> None:
        """
        滑鼠左鍵按住 (可指定元素或當前位置)
        Left click and hold mouse at current position or on a given element
        """
        web_runner_logger.info(f"WebDriverWrapper left_click_and_hold, on_element: {on_element}")
        param = locals()
        try:
            self._action_chain.click_and_hold(on_element)
            record_action_to_list("webdriver wrapper left_click_and_hold", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper left_click_and_hold failed: {repr(error)}")
            record_action_to_list("webdriver wrapper left_click_and_hold", param, error)

    def left_click_and_hold_with_test_object(self, element_name: str = None) -> None:
        """
        使用 TestObject 名稱找到元素並左鍵按住
        Left click and hold using a TestObject name
        """
        web_runner_logger.info(f"WebDriverWrapper left_click_and_hold_with_test_object, element_name: {element_name}")
        param = locals()
        try:
            if element_name is None:
                self._action_chain.click_and_hold(None)
            else:
                record = test_object_record.test_object_record_dict.get(element_name)
                if record is None:
                    raise WebRunnerException(f"TestObject '{element_name}' not found")
                element = self.current_webdriver.find_element(record.test_object_type, record.test_object_name)
                self._action_chain.click_and_hold(element)
            record_action_to_list("webdriver wrapper left_click_and_hold_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper left_click_and_hold_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper left_click_and_hold_with_test_object", param, error)

    def right_click(self, on_element: WebElement = None) -> None:
        """
        滑鼠右鍵點擊 (可指定元素或當前位置)
        Right click mouse at current position or on a given element
        """
        web_runner_logger.info(f"WebDriverWrapper right_click, on_element: {on_element}")
        param = locals()
        try:
            self._action_chain.context_click(on_element)
            record_action_to_list("webdriver wrapper right_click", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper right_click failed: {repr(error)}")
            record_action_to_list("webdriver wrapper right_click", param, error)

    def right_click_with_test_object(self, element_name: str = None) -> None:
        """
        使用 TestObject 名稱找到元素並右鍵點擊
        Right click using a TestObject name
        """
        web_runner_logger.info(f"WebDriverWrapper right_click_with_test_object, element_name: {element_name}")
        param = locals()
        try:
            if element_name is None:
                self._action_chain.context_click(None)
            else:
                record = test_object_record.test_object_record_dict.get(element_name)
                if record is None:
                    raise WebRunnerException(f"TestObject '{element_name}' not found")
                element = self.current_webdriver.find_element(record.test_object_type, record.test_object_name)
                self._action_chain.context_click(element)
            record_action_to_list("webdriver wrapper right_click_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper right_click_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper right_click_with_test_object", param, error)

    def left_double_click(self, on_element: WebElement = None) -> None:
        """
        滑鼠左鍵雙擊 (可指定元素或當前位置)
        Double left click mouse at current position or on a given element

        :param on_element: WebElement 或 None
        """
        web_runner_logger.info(f"WebDriverWrapper left_double_click, on_element: {on_element}")
        param = locals()
        try:
            self._action_chain.double_click(on_element)
            record_action_to_list("webdriver wrapper left_double_click", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper left_double_click failed: {repr(error)}")
            record_action_to_list("webdriver wrapper left_double_click", param, error)

    def left_double_click_with_test_object(self, element_name: str = None) -> None:
        """
        使用 TestObject 名稱找到元素並左鍵雙擊
        Double left click using a TestObject name

        :param element_name: 測試物件名稱 / test object name
        """
        web_runner_logger.info(f"WebDriverWrapper left_double_click_with_test_object, element_name: {element_name}")
        param = locals()
        try:
            if element_name is None:
                self._action_chain.double_click(None)
            else:
                record = test_object_record.test_object_record_dict.get(element_name)
                if record is None:
                    raise WebRunnerException(f"TestObject '{element_name}' not found")
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    record.test_object_type, record.test_object_name
                )
                self._action_chain.double_click(web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper left_double_click_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper left_double_click_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper left_double_click_with_test_object", param, error)

    def release(self, on_element: WebElement = None) -> None:
        """
        釋放滑鼠 (可指定元素或當前位置)
        Release mouse button at current position or on a given element
        """
        web_runner_logger.info(f"WebDriverWrapper release, on_element: {on_element}")
        param = locals()
        try:
            self._action_chain.release(on_element)
            record_action_to_list("webdriver wrapper release", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper release failed: {repr(error)}")
            record_action_to_list("webdriver wrapper release", param, error)

    def release_with_test_object(self, element_name: str = None) -> None:
        """
        使用 TestObject 名稱找到元素並釋放滑鼠
        Release mouse button using a TestObject name
        """
        web_runner_logger.info(f"WebDriverWrapper release_with_test_object, element_name: {element_name}")
        param = locals()
        try:
            if element_name is None:
                self._action_chain.release(None)
            else:
                record = test_object_record.test_object_record_dict.get(element_name)
                if record is None:
                    raise WebRunnerException(f"TestObject '{element_name}' not found")
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    record.test_object_type, record.test_object_name
                )
                self._action_chain.release(web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper release_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper release_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper release_with_test_object", param, error)

    def press_key(self, keycode_on_key_class, on_element: WebElement = None) -> None:
        """
        按下鍵盤按鍵 (可指定元素或當前位置)
        Press a key on keyboard, optionally on a given element

        :param keycode_on_key_class: 要按下的鍵 (來自 selenium.webdriver.common.keys.Keys)
                                     key to press (from selenium.webdriver.common.keys.Keys)
        :param on_element: WebElement 或 None
        """
        web_runner_logger.info(
            f"WebDriverWrapper press_key, keycode_on_key_class: {keycode_on_key_class}, on_element: {on_element}"
        )
        param = locals()
        try:
            self._action_chain.key_down(keycode_on_key_class, on_element)
            record_action_to_list("webdriver wrapper press_key", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper press_key failed: {repr(error)}")
            record_action_to_list("webdriver wrapper press_key", param, error)

    def press_key_with_test_object(self, keycode_on_key_class, element_name: str = None) -> None:
        """
        使用 TestObject 名稱找到元素並按下鍵盤按鍵
        Press a key on keyboard using a TestObject name

        :param keycode_on_key_class: 要按下的鍵 (selenium Keys)
        :param element_name: 測試物件名稱 / test object name
        """
        web_runner_logger.info(
            f"WebDriverWrapper press_key_with_test_object, keycode_on_key_class: {keycode_on_key_class}, element_name: {element_name}"
        )
        param = locals()
        try:
            if element_name is None:
                self._action_chain.key_down(keycode_on_key_class, None)
            else:
                record = test_object_record.test_object_record_dict.get(element_name)
                if record is None:
                    raise WebRunnerException(f"TestObject '{element_name}' not found")
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    record.test_object_type, record.test_object_name
                )
                self._action_chain.key_down(keycode_on_key_class, web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper press_key_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper press_key_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper press_key_with_test_object", param, error)

    def release_key(self, keycode_on_key_class, on_element: WebElement = None) -> None:
        """
        釋放鍵盤按鍵 (可指定元素或當前位置)
        Release a key on keyboard, optionally on a given element

        :param keycode_on_key_class: 要釋放的鍵 (selenium Keys)
        :param on_element: WebElement 或 None
        """
        web_runner_logger.info(
            f"WebDriverWrapper release_key, keycode_on_key_class: {keycode_on_key_class}, on_element: {on_element}"
        )
        param = locals()
        try:
            self._action_chain.key_up(keycode_on_key_class, on_element)
            record_action_to_list("webdriver wrapper release_key", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper release_key failed: {repr(error)}")
            record_action_to_list("webdriver wrapper release_key", param, error)

    def release_key_with_test_object(self, keycode_on_key_class, element_name: str = None) -> None:
        """
        使用 TestObject 名稱找到元素並釋放鍵盤按鍵
        Release a key on keyboard using a TestObject name

        :param keycode_on_key_class: 要釋放的鍵 (selenium Keys)
        :param element_name: 測試物件名稱 / test object name
        """
        web_runner_logger.info(
            f"WebDriverWrapper release_key_with_test_object, keycode_on_key_class: {keycode_on_key_class}, element_name: {element_name}"
        )
        param = locals()
        try:
            if element_name is None:
                self._action_chain.key_up(keycode_on_key_class, None)
            else:
                record = test_object_record.test_object_record_dict.get(element_name)
                if record is None:
                    raise WebRunnerException(f"TestObject '{element_name}' not found")
                web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                    record.test_object_type, record.test_object_name
                )
                self._action_chain.key_up(keycode_on_key_class, web_element_wrapper.current_web_element)
            record_action_to_list("webdriver wrapper release_key_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper release_key_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper release_key_with_test_object", param, error)

    def move_by_offset(self, offset_x: int, offset_y: int) -> None:
        """
        滑鼠移動指定偏移量
        Move mouse by offset

        :param offset_x: X 軸偏移量 / offset on X axis
        :param offset_y: Y 軸偏移量 / offset on Y axis
        """
        web_runner_logger.info(f"WebDriverWrapper move_by_offset, offset_x: {offset_x}, offset_y: {offset_y}")
        param = locals()
        try:
            self._action_chain.move_by_offset(offset_x, offset_y)
            record_action_to_list("webdriver wrapper move_by_offset", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper move_by_offset failed: {repr(error)}")
            record_action_to_list("webdriver wrapper move_by_offset", param, error)

    def pause(self, seconds: int) -> None:
        """
        暫停指定秒數 (注意：可能導致 Selenium 拋出例外)
        Pause for a number of seconds (may cause Selenium exceptions)

        :param seconds: 暫停秒數 / seconds to pause
        """
        web_runner_logger.info(f"WebDriverWrapper pause, seconds: {seconds}")
        param = locals()
        try:
            self._action_chain.pause(seconds)
            record_action_to_list("webdriver wrapper pause", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper pause failed: {repr(error)}")
            record_action_to_list("webdriver wrapper pause", param, error)

    def send_keys(self, keys_to_send) -> None:
        """
        發送鍵盤按鍵 (按下並釋放)
        Send (press and release) keyboard keys

        :param keys_to_send: 要發送的鍵 (可多個) / keys to send (can be multiple)
        """
        web_runner_logger.info(f"WebDriverWrapper send_keys, keys_to_send: {keys_to_send}")
        param = locals()
        try:
            self._action_chain.send_keys(*keys_to_send)
            record_action_to_list("webdriver wrapper send_keys", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper send_keys failed: {repr(error)}")
            record_action_to_list("webdriver wrapper send_keys", param, error)

    def send_keys_to_element(self, element: WebElement, keys_to_send) -> None:
        """
        發送鍵盤按鍵到指定元素
        Send keyboard keys to a given element

        :param element: 目標元素 / target element
        :param keys_to_send: 要發送的鍵 / keys to send
        """
        web_runner_logger.info(
            f"WebDriverWrapper send_keys_to_element, element: {element}, keys_to_send: {keys_to_send}")
        param = locals()
        try:
            self._action_chain.send_keys_to_element(element, keys_to_send)
            record_action_to_list("webdriver wrapper send_keys_to_element", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper send_keys_to_element failed: {repr(error)}")
            record_action_to_list("webdriver wrapper send_keys_to_element", param, error)

    def send_keys_to_element_with_test_object(self, element_name: str, keys_to_send) -> None:
        """
        使用 TestObject 名稱找到元素並發送鍵盤按鍵
        Send keyboard keys to an element using a TestObject name

        :param element_name: 測試物件名稱 / test object name
        :param keys_to_send: 要發送的鍵 / keys to send
        """
        web_runner_logger.info(
            f"WebDriverWrapper send_keys_to_element_with_test_object, element_name: {element_name}, keys_to_send: {keys_to_send}"
        )
        param = locals()
        try:
            record = test_object_record.test_object_record_dict.get(element_name)
            if record is None:
                raise WebRunnerException(f"TestObject '{element_name}' not found")
            web_element_wrapper.current_web_element = self.current_webdriver.find_element(
                record.test_object_type, record.test_object_name
            )
            self._action_chain.send_keys_to_element(web_element_wrapper.current_web_element, *keys_to_send)
            record_action_to_list("webdriver wrapper send_keys_to_element_with_test_object", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper send_keys_to_element_with_test_object failed: {repr(error)}")
            record_action_to_list("webdriver wrapper send_keys_to_element_with_test_object", param, error)

    def scroll(self, scroll_x: int, scroll_y: int) -> None:
        """
        滾動頁面
        Scroll the page

        :param scroll_x: 滾動的 X 軸距離 / distance to scroll on X axis
        :param scroll_y: 滾動的 Y 軸距離 / distance to scroll on Y axis
        """
        web_runner_logger.info(
            f"WebDriverWrapper scroll, scroll_x: {scroll_x}, scroll_y: {scroll_y}"
        )
        param = locals()
        try:
            self._action_chain.scroll_by_amount(scroll_x, scroll_y)
            record_action_to_list("webdriver wrapper scroll", param, None)
        except Exception as error:
            web_runner_logger.error(f"WebDriverWrapper scroll failed: {repr(error)}")
            record_action_to_list("webdriver wrapper scroll", param, error)
