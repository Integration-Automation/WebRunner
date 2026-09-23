"""The public API this project promises (README › Public API & Deprecation Policy).

Everything checked here is something another repository already imports, or something the README
tells users to import. Removing or renaming one of them is a breaking change that has to go through
the deprecation policy, so this file fails first (workspace item X-3).
"""
import importlib

import pytest

import je_web_runner

# Named in the README as the canonical entry points, and imported by TestPioneer, PyBreeze,
# AutoControlGUI and Jeffrey_RPA.
PROMISED_TOP_LEVEL = (
    "webdriver_wrapper_instance", "web_element_wrapper", "get_webdriver_manager",
    "set_webdriver_options_argument", "TestObject", "create_test_object",
    "get_test_object_type_list", "execute_action", "execute_files", "executor",
    "add_command_to_executor", "read_action_json", "get_dir_files_as_list",
    "create_project_dir", "test_record_instance", "callback_executor", "Keys",
    "web_runner_logger",
    "start_web_runner_socket_server", "send_command", "read_frame", "encode_frame",
    "generate_html_report", "generate_json_report", "generate_xml_report",
    "generate_junit_xml_report", "generate_allure_report",
)

# Module paths other repositories import directly. The logging module's name is misspelled in the
# original code and stays that way: Jeffrey_RPA's conftest hooks that exact string.
SUPPORTED_MODULE_PATHS = {
    "je_web_runner.utils.executor.action_executor": ("executor", "execute_action", "execute_files"),
    "je_web_runner.utils.logging.loggin_instance": ("web_runner_logger", "WebRunnerLoggingHandler"),
    "je_web_runner.webdriver.webdriver_wrapper": (
        "WebDriverWrapper", "webdriver_wrapper_instance",
        "_options_dict", "_webdriver_dict", "_webdriver_manager_dict",
    ),
}

# The four wrapper methods Jeffrey_RPA requires >=0.0.88 for (architecture.md §6).
REQUIRED_WRAPPER_METHODS = (
    "get_current_url", "get_title", "save_screenshot", "add_script_to_evaluate_on_new_document",
)


@pytest.mark.parametrize("name", PROMISED_TOP_LEVEL)
def test_promised_name_is_exported(name):
    assert name in je_web_runner.__all__, f"{name} left __all__"  # nosec B101
    assert getattr(je_web_runner, name) is not None  # nosec B101


def test_every_exported_name_resolves():
    missing = [name for name in je_web_runner.__all__ if not hasattr(je_web_runner, name)]
    assert missing == []  # nosec B101


def test_all_has_no_duplicates():
    duplicates = {name for name in je_web_runner.__all__ if je_web_runner.__all__.count(name) > 1}
    assert duplicates == set()  # nosec B101


@pytest.mark.parametrize("path, attributes", sorted(SUPPORTED_MODULE_PATHS.items()))
def test_supported_module_path_keeps_its_attributes(path, attributes):
    module = importlib.import_module(path)  # nosemgrep
    missing = [attribute for attribute in attributes if not hasattr(module, attribute)]
    assert missing == [], f"{path} lost {missing}"  # nosec B101


@pytest.mark.parametrize("method", REQUIRED_WRAPPER_METHODS)
def test_wrapper_method_required_by_jeffrey_rpa(method):
    assert callable(getattr(je_web_runner.webdriver_wrapper_instance, method))  # nosec B101


def test_executor_commands_are_wr_prefixed_and_include_the_core_set():
    commands = {name for name in je_web_runner.executor.event_dict if name.startswith("WR_")}
    core = {"WR_to_url", "WR_click_element", "WR_input_to_element", "WR_get_current_url",
            "WR_get_title", "WR_save_screenshot"}
    assert core <= commands, sorted(core - commands)  # nosec B101
