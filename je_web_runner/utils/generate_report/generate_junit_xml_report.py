"""
產生 JUnit 格式 XML 測試報告，便於 GitHub Actions / Jenkins 等 CI 系統消費。
Generate JUnit-format XML test reports for CI consumption (GitHub Actions, Jenkins, etc.).
"""
from threading import Lock
# Element/SubElement/tostring are XML builders, not parsers; defusedxml does not provide builders.
from xml.etree.ElementTree import Element, SubElement, tostring  # nosec B405 # nosemgrep: use-defused-xml

from je_web_runner.utils.exception.exception_tags import cant_generate_json_report
from je_web_runner.utils.exception.exceptions import WebRunnerGenerateJsonReportException
from je_web_runner.utils.logging.loggin_instance import web_runner_logger
from je_web_runner.utils.test_record.test_record_class import test_record_instance

_lock = Lock()

_NO_EXCEPTION_MARKER = "None"


def _record_is_failure(record: dict) -> bool:
    """Whether the record represents a failed action."""
    return record.get("program_exception", _NO_EXCEPTION_MARKER) != _NO_EXCEPTION_MARKER


def _build_testcase(suite: Element, record: dict, index: int) -> None:
    """Append a single <testcase> child to the given <testsuite>."""
    function_name = str(record.get("function_name", "unknown"))
    testcase = SubElement(
        suite,
        "testcase",
        {
            "name": f"{function_name}_{index}",
            "classname": f"webrunner.{function_name}",
            "time": "0",
        },
    )
    if _record_is_failure(record):
        failure = SubElement(
            testcase,
            "failure",
            {
                "message": str(record.get("program_exception", "")),
                "type": "WebRunnerExecutionError",
            },
        )
        failure.text = (
            f"function: {function_name}\n"
            f"param: {record.get('local_param')}\n"
            f"time: {record.get('time')}\n"
            f"exception: {record.get('program_exception')}"
        )


def generate_junit_xml() -> str:
    """
    產生 JUnit 格式 XML 字串
    Generate JUnit-format XML string

    :return: JUnit XML 字串 / JUnit XML string
    """
    web_runner_logger.info("generate_junit_xml")

    records = test_record_instance.test_record_list
    if len(records) == 0:
        raise WebRunnerGenerateJsonReportException(cant_generate_json_report)

    failures = sum(1 for record in records if _record_is_failure(record))
    total = len(records)
    attrs = {
        "name": "webrunner",
        "tests": str(total),
        "failures": str(failures),
        "errors": "0",
        "time": "0",
    }
    suites = Element("testsuites", attrs)
    suite = SubElement(suites, "testsuite", attrs)
    for index, record in enumerate(records, start=1):
        _build_testcase(suite, record, index)

    return str(tostring(suites, encoding="utf-8"), encoding="utf-8")


def generate_junit_xml_report(junit_file_name: str = "default_name") -> None:
    """
    產生並輸出 JUnit XML 測試報告
    Generate and save a JUnit XML test report

    :param junit_file_name: 輸出檔案名稱 (不含副檔名)
                            Output file name (without extension)
    """
    web_runner_logger.info(f"generate_junit_xml_report, junit_file_name: {junit_file_name}")

    junit_xml = generate_junit_xml()
    target = junit_file_name + "_junit.xml"
    try:
        _lock.acquire()
        with open(target, "w+", encoding="utf-8") as file_to_write:
            file_to_write.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            file_to_write.write(junit_xml)
    except OSError as error:
        web_runner_logger.error(
            f"generate_junit_xml_report, junit_file_name: {junit_file_name}, failed: {repr(error)}"
        )
    finally:
        _lock.release()
