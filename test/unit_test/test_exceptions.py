import unittest

from je_web_runner.utils.exception.exceptions import (
    WebRunnerException,
    WebRunnerWebDriverNotFoundException,
    WebRunnerOptionsWrongTypeException,
    WebRunnerArgumentWrongTypeException,
    WebRunnerWebDriverIsNoneException,
    WebRunnerExecuteException,
    WebRunnerJsonException,
    WebRunnerGenerateJsonReportException,
    WebRunnerAssertException,
    WebRunnerHTMLException,
    WebRunnerAddCommandException,
    XMLException,
    XMLTypeException,
    CallbackExecutorException,
)


class TestExceptionHierarchy(unittest.TestCase):

    def test_all_exceptions_inherit_from_base(self):
        exceptions = [
            WebRunnerWebDriverNotFoundException,
            WebRunnerOptionsWrongTypeException,
            WebRunnerArgumentWrongTypeException,
            WebRunnerWebDriverIsNoneException,
            WebRunnerExecuteException,
            WebRunnerJsonException,
            WebRunnerAssertException,
            WebRunnerHTMLException,
            WebRunnerAddCommandException,
            XMLException,
            CallbackExecutorException,
        ]
        for exc_class in exceptions:
            self.assertTrue(
                issubclass(exc_class, WebRunnerException),
                f"{exc_class.__name__} should inherit from WebRunnerException"
            )

    def test_json_report_exception_inherits_from_json(self):
        self.assertTrue(issubclass(WebRunnerGenerateJsonReportException, WebRunnerJsonException))

    def test_xml_type_exception_inherits_from_xml(self):
        self.assertTrue(issubclass(XMLTypeException, XMLException))

    def test_exceptions_are_catchable(self):
        with self.assertRaises(WebRunnerException):
            raise WebRunnerExecuteException("test")

    def test_exception_message(self):
        try:
            raise WebRunnerExecuteException("test message")
        except WebRunnerExecuteException as e:
            self.assertEqual(str(e), "test message")


if __name__ == "__main__":
    unittest.main()
