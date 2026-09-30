"""
The Playwright commands added for Selenium parity, against a real headless Chromium.

The unit tests mock Playwright, which cannot catch a wrong real-API call. This drives
the wrapper through action JSON on local ``data:`` pages. It skips when Playwright or
its Chromium build is not installed (CI installs neither).
"""
import base64
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.parse import quote

import pytest

pytest.importorskip("playwright.sync_api", reason="Playwright is optional")

from je_web_runner.utils.executor.action_executor import executor  # noqa: E402
from je_web_runner.webdriver.playwright_wrapper import playwright_wrapper_instance  # noqa: E402

_FRAME = "<form id='f'><label>Card <input id='card' name='card'></label><button>Pay</button></form>"
_PAGE = (
    "<html><head><title>Shop checkout</title></head><body style='height:3000px'>"
    "<button id='ask' onclick=\"document.getElementById('out').textContent = prompt('Name?')\">Ask</button>"
    "<p id='out'></p><div id='box' style='position:absolute;left:10px;top:200px;width:50px;height:50px'></div>"
    f"<iframe id='pay' srcdoc=\"{_FRAME}\"></iframe></body></html>"
)


def _data_url(html: str) -> str:
    return "data:text/html," + quote(html)


def _run(actions):
    record, failed = executor.collect_action_results(actions)
    assert failed == [], {key: record[key] for key in failed}  # nosec B101
    return list(record.values())


class TestRealBrowser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            playwright_wrapper_instance.launch(browser="chromium", headless=True,
                                               context_options={"timezone_id": "UTC"})
        except Exception as error:  # the browser build is not installed here
            raise unittest.SkipTest(f"Chromium for Playwright is not available: {error!r}")
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        playwright_wrapper_instance.quit()
        cls.tmp.cleanup()

    def setUp(self):
        _run([["WR_pw_to_url", {"url": _data_url(_PAGE)}]])

    def test_frame_role_lookup_and_assertions(self):
        _run([
            ["WR_pw_switch_to_frame", {"selectors": "#pay"}],
            ["WR_pw_fill", {"selector": "#card", "value": "4242"}],
            ["WR_pw_find_by", {"by": "role", "value": "button", "name": "Pay"}],
            ["WR_pw_element_assert", {"check_dict": {"tag_name": "button", "text": "Pay"}}],
            ["WR_pw_find_by", {"by": "label", "value": "Card"}],
            ["WR_pw_element_assert", {"check_dict": {"value": "4242"}}],
            ["WR_pw_switch_to_main_frame"],
            ["WR_pw_check_current_page", {"check_dict": {"title": "Shop checkout"}}],
        ])
        _record, failed = executor.collect_action_results(
            [["WR_pw_check_current_page", {"check_dict": {"title": "Elsewhere"}}]])
        self.assertEqual(len(failed), 1)

    def test_dialog_policy_answers_a_prompt(self):
        _run([
            ["WR_pw_set_dialog_policy", {"action": "accept", "prompt_text": "Ann"}],
            ["WR_pw_click", {"selector": "#ask"}],
        ])
        self.assertEqual(playwright_wrapper_instance.page.text_content("#out"), "Ann")
        self.assertEqual(playwright_wrapper_instance.last_dialog()["type"], "prompt")

    def test_cookies_by_name(self):
        playwright_wrapper_instance.add_cookies([
            {"name": "sid", "value": "1", "url": "https://example.com"},
            {"name": "keep", "value": "2", "url": "https://example.com"},
        ])
        values = _run([["WR_pw_get_cookie", {"name": "sid"}], ["WR_pw_delete_cookie", {"name": "sid"}]])
        self.assertEqual(values[0]["value"], "1")
        names = {cookie["name"] for cookie in playwright_wrapper_instance.get_cookies()}
        self.assertEqual(names, {"keep"})

    def test_page_commands(self):
        pdf = str(Path(self.tmp.name) / "page.pdf")
        values = _run([
            ["WR_pw_scroll", {"scroll_x": 0, "scroll_y": 500}],
            ["WR_pw_screenshot_base64"],
            ["WR_pw_print_page", {"file_path": pdf}],
            ["WR_pw_switch_to_page_by_title", {"pattern": "checkout"}],
        ])
        self.assertTrue(base64.b64decode(values[1]).startswith(b"\x89PNG"))
        self.assertTrue(Path(pdf).read_bytes().startswith(b"%PDF"))
        self.assertTrue(values[3])

    def test_init_script_survives_a_context_rebuild(self):
        _run([
            ["WR_pw_add_init_script", {"source": "window.__probe = 42;"}],
            ["WR_pw_set_locale", {"locale": "de-DE"}],
            ["WR_pw_to_url", {"url": _data_url("<p>x</p>")}],
        ])
        self.assertEqual(playwright_wrapper_instance.evaluate("window.__probe"), 42)
        self.assertEqual(playwright_wrapper_instance.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone"),
                         "UTC")

    def test_trace_and_storage_state(self):
        trace = str(Path(self.tmp.name) / "run.zip")
        state = str(Path(self.tmp.name) / "state.json")
        _run([
            ["WR_pw_tracing_start"],
            ["WR_pw_click", {"selector": "#box"}],
            ["WR_pw_tracing_stop", {"path": trace}],
            ["WR_pw_save_storage_state", {"path": state}],
        ])
        self.assertTrue(zipfile.is_zipfile(trace))
        self.assertTrue(Path(state).is_file())

    def test_download_and_cache_switch(self):
        link = "<a id='dl' download='hello.txt' href='data:text/plain,hello'>get</a>"
        saved = _run([
            ["WR_pw_to_url", {"url": _data_url(link)}],
            ["WR_pw_set_cache_disabled", {"disabled": True}],
            ["WR_pw_download", {"selector": "#dl", "save_to": self.tmp.name}],
            ["WR_pw_set_cache_disabled", {"disabled": False}],
        ])[2]
        self.assertEqual(Path(saved).name, "hello.txt")
        self.assertEqual(Path(saved).read_text(encoding="utf-8"), "hello")

    def test_recorder_and_visual_regression(self):
        pytest.importorskip("PIL", reason="visual regression needs Pillow")
        baseline = str(Path(self.tmp.name) / "base.png")
        values = _run([
            ["WR_pw_recorder_start"],
            ["WR_pw_click", {"selector": "#box"}],
            ["WR_pw_recorder_pull_events"],
            ["WR_pw_recorder_stop"],
            ["WR_pw_visual_capture_baseline", {"baseline_path": baseline}],
            ["WR_pw_visual_compare", {"baseline_path": baseline}],
        ])
        self.assertTrue(any(event.get("type") == "click" for event in values[2]))
        self.assertTrue(values[5]["match"])


class TestPersistentProfile(unittest.TestCase):

    def test_launch_persistent_and_fixed_options(self):
        from je_web_runner.webdriver.playwright_wrapper import PlaywrightBackendError, PlaywrightWrapper
        wrapper = PlaywrightWrapper()
        with tempfile.TemporaryDirectory() as profile:
            try:
                wrapper.launch_persistent(profile, headless=True, locale="fr-FR")
            except PlaywrightBackendError:
                raise
            except Exception as error:  # the browser build is not installed here
                raise unittest.SkipTest(f"Chromium for Playwright is not available: {error!r}")
            try:
                self.assertEqual(wrapper.evaluate("navigator.language"), "fr-FR")
                with self.assertRaises(PlaywrightBackendError):
                    wrapper.set_timezone("UTC")
            finally:
                wrapper.quit()


if __name__ == "__main__":
    unittest.main()
