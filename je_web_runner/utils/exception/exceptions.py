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


# Json

class WebRunnerJsonException(WebRunnerException):
    pass


class WebRunnerGenerateJsonReportException(WebRunnerJsonException):
    pass


class WebRunnerAssertException(WebRunnerException):
    pass


class WebRunnerHTMLException(WebRunnerException):
    pass


class WebRunnerAddCommandException(WebRunnerException):
    pass


# XML

class XMLException(WebRunnerException):
    pass


class XMLTypeException(XMLException):
    pass


class CallbackExecutorException(WebRunnerException):
    pass


def describe_error(error: BaseException | None) -> str:
    """
    例外的一行描述，保證含訊息
    ``repr(error)``, unless that leaves the message out, as Selenium's exceptions do
    (``WebDriverException()``): then ``Type('message')``, with Selenium's ``msg`` (without
    its stack trace) as the message. ``None`` gives ``"None"``, as the test record expects.
    """
    text = repr(error)
    if error is None:
        return text
    message = error.msg if hasattr(error, "msg") else str(error).strip()  # Selenium's str() adds "Message: "
    if not message or str(message) in text:
        return text
    return f"{type(error).__name__}({str(message)!r})"
