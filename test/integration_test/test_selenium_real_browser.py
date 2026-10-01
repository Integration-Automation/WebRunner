"""
The Selenium commands added for Playwright parity, against a real headless Chrome.

The unit tests mock the driver. This drives action JSON on local ``data:`` pages and
skips when Chrome or its driver cannot start (CI's integration job has no browser).
"""
import unittest
from urllib.parse import quote

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver.webdriver_wrapper import webdriver_wrapper_instance

_PAGE = (
    "<html><head><title>Parity page</title></head><body>"
    "<label><input id='agree' type='checkbox'> Agree</label>"
    "<button id='ask' onclick=\"document.getElementById('out').textContent = prompt('Name?')\">Ask</button>"
    "<p id='out'></p><div id='late'></div>"
    "<script>setTimeout(() => { document.getElementById('late').innerHTML = '<b>ready</b>'; }, 300);</script>"
    "</body></html>"
)


def _run(actions):
    record, failed = executor.collect_action_results(actions)
    assert failed == [], {key: record[key] for key in failed}  # nosec B101
    return list(record.values())


class TestSeleniumRealBrowser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            from selenium import webdriver
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            webdriver_wrapper_instance.current_webdriver = webdriver.Chrome(options=options)
        except Exception as error:  # no Chrome or chromedriver here
            raise unittest.SkipTest(f"Chrome for Selenium is not available: {error!r}")

    @classmethod
    def tearDownClass(cls):
        webdriver_wrapper_instance.current_webdriver.quit()
        webdriver_wrapper_instance.current_webdriver = None

    def setUp(self):
        webdriver_wrapper_instance.current_webdriver.get("data:text/html," + quote(_PAGE))

    def test_waits_raw_selectors_and_element_commands(self):
        values = _run([
            ["WR_wait_for_ready_state"],
            ["WR_wait_for_title", {"pattern": "Parity"}],
            ["WR_find_element_by", {"selector": "#agree"}],
            ["WR_element_check"],
            ["WR_wait_for_element", {"selector": "#late b", "timeout": 5}],
            ["WR_element_inner_text"],
            ["WR_find_element_by", {"selector": "late", "by": "id"}],
            ["WR_element_inner_html"],
        ])
        self.assertEqual(values[5], "ready")
        self.assertEqual(values[7], "<b>ready</b>")
        agree = webdriver_wrapper_instance.current_webdriver.find_element("id", "agree")
        self.assertTrue(agree.is_selected())

    def test_a_failed_wait_fails_its_action(self):
        _record, failed = executor.collect_action_results(
            [["WR_wait_for_element", {"selector": "#never", "timeout": 0.5}]])
        self.assertEqual(len(failed), 1)

    def test_prompt(self):
        values = _run([
            ["WR_find_element_by", {"selector": "#ask"}],
            ["WR_element_click"],
            ["WR_alert_text"],
            ["WR_alert_accept", {"prompt_text": "Ann"}],
        ])
        self.assertEqual(values[2], "Name?")
        self.assertEqual(webdriver_wrapper_instance.current_webdriver.find_element("id", "out").text, "Ann")

    def test_cdp_device_permissions_and_clock(self):
        device = "Pixel 8"  # a touch device
        self.assertIn(device, webdriver_wrapper_instance.list_devices())
        _run([
            ["WR_emulate_device", {"name": device}],
            ["WR_grant_permissions", {"permissions": ["geolocation"]}],
            ["WR_clock_freeze", {"moment": "2026-01-01T00:00:00Z"}],
        ])
        driver = webdriver_wrapper_instance.current_webdriver
        self.assertEqual(driver.execute_script("return Date.now()"), 1767225600000)
        driver.get("data:text/html,<p>reloaded</p>")  # touch and the frozen clock apply to new documents too
        self.assertEqual(driver.execute_script("return Date.now()"), 1767225600000)
        self.assertGreater(driver.execute_script("return navigator.maxTouchPoints"), 0)
        self.assertEqual(driver.execute_script("return screen.width"), 412)


if __name__ == "__main__":
    unittest.main()
