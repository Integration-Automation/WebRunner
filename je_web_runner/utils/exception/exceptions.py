class WebDriverException(Exception):
    pass


class WebDriverNotFoundException(WebDriverException):
    pass


class OptionsWrongTypeException(WebDriverException):
    pass


class ArgumentWrongTypeException(WebDriverException):
    pass


class WebDriverIsNoneException(WebDriverException):
    pass


class WebRunnerExecuteException(WebDriverException):
    pass


class WebRunnerJsonException(WebDriverException):
    pass


class AssertException(WebDriverException):
    pass


class HTMLException(WebDriverException):
    pass
