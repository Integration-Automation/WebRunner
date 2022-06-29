class WebRunnerException(Exception):
    pass


class WebRunnerWebDriverNotFoundException(WebRunnerException):
    pass


class WebRunnerOptionsWrongTypeException(WebRunnerException):
    pass


class WebRunnerArgumentWrongTypeException(WebRunnerException):
    pass


class WebRunnerWebDriverIsNoneException(WebRunnerException):
    pass


class WebRunnerExecuteException(WebRunnerException):
    pass


class WebRunnerJsonException(WebRunnerException):
    pass


class WebRunnerAssertException(WebRunnerException):
    pass


class WebRunnerHTMLException(WebRunnerException):
    pass


class WebRunnerAddCommandException(WebRunnerException):
    pass
