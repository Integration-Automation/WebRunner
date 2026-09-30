"""Playwright trace-viewer and video recording commands, and traces saved beside failure screenshots."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from je_web_runner.utils.executor.action_executor import executor
from je_web_runner.webdriver import playwright_wrapper as pw_module
from je_web_runner.webdriver.playwright_wrapper import PlaywrightBackendError, PlaywrightWrapper


def _launch():
    contexts = []

    def new_context(**kwargs):
        context = MagicMock()
        context.options = kwargs
        page = MagicMock()
        page.url = "about:blank"
        page.video.path.return_value = f"videos/page{len(contexts)}.webm"
        context.new_page.return_value = page
        contexts.append(context)
        return context

    browser = MagicMock()
    browser.new_context.side_effect = new_context
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    factory = MagicMock()
    factory.start.return_value = playwright
    with patch.object(pw_module, "_require_playwright", return_value=MagicMock(return_value=factory)):
        wrapper = PlaywrightWrapper()
        wrapper.launch(browser="chromium")
    return wrapper, contexts


class TestTracing(unittest.TestCase):

    def test_start_save_and_stop(self):
        wrapper, _contexts = _launch()
        tracing = wrapper.context.tracing
        wrapper.start_tracing()
        tracing.start.assert_called_once_with(screenshots=True, snapshots=True, sources=False)
        tracing.start_chunk.assert_called_once_with()
        self.assertTrue(wrapper.tracing_active)
        wrapper.save_trace_chunk("part.zip")
        tracing.stop_chunk.assert_called_with(path="part.zip")
        self.assertEqual(tracing.start_chunk.call_count, 2)
        self.assertEqual(wrapper.stop_tracing("run.zip"), "run.zip")
        tracing.stop_chunk.assert_called_with(path="run.zip")
        tracing.stop.assert_called_once_with()
        self.assertFalse(wrapper.tracing_active)

    def test_saving_without_tracing_is_an_error(self):
        wrapper, _contexts = _launch()
        with self.assertRaises(PlaywrightBackendError):
            wrapper.save_trace_chunk("x.zip")
        with self.assertRaises(PlaywrightBackendError):
            wrapper.stop_tracing("x.zip")

    def test_tracing_restarts_on_a_rebuilt_context(self):
        wrapper, contexts = _launch()
        wrapper.start_tracing(sources=True)
        wrapper.set_timezone("UTC")
        self.assertEqual(len(contexts), 2)
        contexts[1].tracing.start.assert_called_once_with(screenshots=True, snapshots=True, sources=True)
        self.assertTrue(wrapper.tracing_active)


class TestVideo(unittest.TestCase):

    def test_start_rebuilds_with_video_options_and_stop_returns_the_files(self):
        wrapper, contexts = _launch()
        wrapper.start_video_recording("videos", width=800, height=600)
        self.assertEqual(contexts[-1].options["record_video_dir"], "videos")
        self.assertEqual(contexts[-1].options["record_video_size"], {"width": 800, "height": 600})
        paths = wrapper.stop_video_recording()
        self.assertEqual(paths, ["videos/page1.webm"])
        self.assertNotIn("record_video_dir", contexts[-1].options)


class TestFailureTrace(unittest.TestCase):

    def test_failed_action_saves_a_trace_next_to_the_screenshot(self):
        wrapper = MagicMock()
        wrapper.tracing_active = True
        wrapper._pages = []
        original_dir = executor.failure_screenshot_dir
        self.addCleanup(setattr, executor, "failure_screenshot_dir", original_dir)
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(pw_module, "playwright_wrapper_instance", wrapper), \
                patch("je_web_runner.utils.executor.action_executor._try_selenium_screenshot", return_value=None), \
                patch("je_web_runner.utils.executor.action_executor._try_playwright_screenshot", return_value=None):
            executor.set_failure_screenshot_dir(tmp)
            record, failed = executor.collect_action_results([["WR_no_such_command"]])
            saved = Path(wrapper.save_trace_chunk.call_args.args[0])
            self.assertEqual(saved.parent, Path(tmp).resolve())
            self.assertTrue(saved.name.endswith("_WR_no_such_command.trace.zip"))
        self.assertIn("trace:", record[failed[0]])

    def test_no_trace_when_tracing_is_off(self):
        wrapper = MagicMock()
        wrapper.tracing_active = False
        original_dir = executor.failure_screenshot_dir
        self.addCleanup(setattr, executor, "failure_screenshot_dir", original_dir)
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(pw_module, "playwright_wrapper_instance", wrapper), \
                patch("je_web_runner.utils.executor.action_executor._try_selenium_screenshot", return_value=None), \
                patch("je_web_runner.utils.executor.action_executor._try_playwright_screenshot", return_value=None):
            executor.set_failure_screenshot_dir(tmp)
            executor.collect_action_results([["WR_no_such_command"]])
        wrapper.save_trace_chunk.assert_not_called()


class TestCommands(unittest.TestCase):

    def test_commands_are_registered(self):
        for name in ("WR_pw_tracing_start", "WR_pw_tracing_save_chunk", "WR_pw_tracing_stop",
                     "WR_pw_video_start", "WR_pw_video_stop"):
            self.assertIn(name, executor.event_dict)


if __name__ == "__main__":
    unittest.main()
