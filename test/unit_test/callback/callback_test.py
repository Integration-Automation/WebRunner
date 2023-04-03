from je_web_runner import callback_executor

callback_executor.callback_function(
    trigger_function_name="get_webdriver_manager",
    callback_function=print,
    callback_param_method="args",
    callback_function_param={"": "open driver"},
    **{
        "webdriver_name": "edge"
    }
)

callback_executor.callback_function(
    trigger_function_name="quit",
    callback_function=print,
    callback_param_method="args",
    callback_function_param={"": "quit  driver"},
)

