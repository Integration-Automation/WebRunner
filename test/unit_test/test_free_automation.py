"""Free automation keeps generic Grid support and refuses ambiguous healing."""
from unittest.mock import MagicMock, patch

import pytest

from je_web_runner.utils.cloud_grid.cloud_drivers import CloudGridError, start_remote_driver
from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.utils.self_healing import healing_locator as healing


def test_commercial_commands_are_removed():
    removed = ("browserstack", "saucelabs", "lambdatest", "testrail")
    assert not any(token in name.lower() for name in executor.event_dict for token in removed)
    assert "WR_start_remote_driver" in executor.event_dict
    assert "WR_jira_create_issue" in executor.event_dict


def test_generic_grid_registers_action_chains():
    module = "je_web_runner.utils.cloud_grid.cloud_drivers"
    with patch(module + ".webdriver.Remote") as remote, patch(module + ".webdriver_wrapper_instance") as wrapper:
        result = start_remote_driver("http://localhost:4444/wd/hub", {"browserName": "firefox"})
        assert result is remote.return_value
        wrapper.set_active_driver.assert_called_once_with(result)
        assert remote.call_args.kwargs["options"].capabilities["browserName"] == "firefox"


@pytest.mark.parametrize("url", ["file:///tmp/grid", "https://user:secret@example.test/grid"])
def test_generic_grid_rejects_invalid_urls(url):
    with pytest.raises(CloudGridError):
        start_remote_driver(url, {})


def test_healing_refuses_multiple_actionable_matches():
    module = "je_web_runner.utils.self_healing.healing_locator"
    with patch(module + ".webdriver_wrapper_instance") as wrapper, patch(module + "._candidates") as candidates:
        candidates.return_value = [("ID", "duplicate"), ("NAME", "backup")]
        wrapper.current_webdriver.find_elements.return_value = [MagicMock(), MagicMock()]
        with pytest.raises(healing.AmbiguousLocatorError):
            healing.find_with_healing_selenium("submit")
        assert wrapper.current_webdriver.find_elements.call_count == 1


def test_healing_skips_hidden_or_disabled_elements():
    hidden, disabled, visible = MagicMock(), MagicMock(), MagicMock()
    hidden.is_displayed.return_value = False
    disabled.is_enabled.return_value = False
    module = "je_web_runner.utils.self_healing.healing_locator"
    with patch(module + ".webdriver_wrapper_instance") as wrapper, patch(module + "._candidates") as candidates:
        candidates.return_value = [("ID", "target")]
        wrapper.current_webdriver.find_elements.return_value = [hidden, disabled, visible]
        assert healing.find_with_healing_selenium("submit") is visible
