==================
WebRunner  Executor Example
==================

.. code-block:: python

    """
    command detail on executor doc
    """

    import sys

    from je_web_runner import execute_action

    "some command to execute"
    test_execute_list = [
        ["to_url", {"url": "https://www.google.com"}],
        ["move_to_element", {"element_name": "q"}],
        ["implicitly_wait", {"time_to_wait": 3}],
        ["move_to_element_with_offset", {"element_name": "q", "x": 10, "y": 10}],
        ["move_by_offset", {"x": 10, "y": 10}],
        ["drag_and_drop", {"element_name": "q", "target_element_name": "q"}],
        ["drag_and_drop_offset", {"element_name": "q", "target_x": 10, "target_y": 10}],
        ["perform"],
        ["left_click", {"element_name": "q"}],
        ["release", {"element_name": "q"}],
        ["left_click"],
        ["release"],
        ["left_double_click"],
        ["release"],
        ["left_double_click"],
        ["left_click_and_hold"],
        ["press_key", {"keycode_on_key_class": "\ue031"}],
        ["release_key", {"keycode_on_key_class": "\ue031"}],
        ["send_keys", {"keys_to_send": "\ue031"}],
        ["send_keys_to_element", {"element_name": "q", "keys_to_send": "\ue031"}],
        ["perform"],
        ["pause", {"seconds": "3"}],
    ]
    "then execute action"
    execute_action(test_execute_list)