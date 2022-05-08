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
