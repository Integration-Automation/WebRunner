import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.cli.cli_main import _build_parser, _parse_execute_str, main
from je_web_runner.utils.exception.exceptions import WebRunnerExecuteException


def _write_action_json(directory: str, name: str, action: list) -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as file_to_write:
        json.dump(action, file_to_write)
    return path


class TestCliParser(unittest.TestCase):

    def test_default_parallel_is_one(self):
        parser = _build_parser()
        args = parser.parse_args(["-e", "x.json"])
        self.assertEqual(args.parallel, 1)
        self.assertEqual(args.parallel_mode, "thread")

    def test_parallel_mode_process_accepted(self):
        parser = _build_parser()
        args = parser.parse_args(["-d", "tests", "--parallel-mode", "process"])
        self.assertEqual(args.parallel_mode, "process")

    def test_validate_and_report_flags(self):
        parser = _build_parser()
        args = parser.parse_args(["--validate", "x.json", "--report", "out"])
        self.assertEqual(args.validate, "x.json")
        self.assertEqual(args.report, "out")

    def test_main_without_args_raises(self):
        with self.assertRaises(WebRunnerExecuteException):
            main([])


class TestCliDispatch(unittest.TestCase):

    def test_validate_calls_validator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_action_json(tmpdir, "ok.json", [["WR_quit"]])
            with patch("je_web_runner.utils.cli.cli_main.validate_action_file") as validate:
                main(["--validate", path])
                validate.assert_called_once_with(path)

    def test_execute_file_invokes_execute_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_action_json(tmpdir, "run.json", [["WR_quit"]])
            with patch("je_web_runner.utils.cli.cli_main.execute_action") as exec_mock:
                main(["-e", path])
                self.assertEqual(exec_mock.call_count, 1)

    def test_parallel_execution_uses_thread_pool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_action_json(tmpdir, "a.json", [["WR_quit"]])
            _write_action_json(tmpdir, "b.json", [["WR_quit"]])
            with patch("je_web_runner.utils.cli.cli_main.execute_action") as exec_mock, \
                    patch("je_web_runner.utils.cli.cli_main.read_action_json", return_value=[["WR_quit"]]):
                main(["-d", tmpdir, "--parallel", "2"])
                self.assertEqual(exec_mock.call_count, 2)

    def test_parallel_mode_process_uses_process_pool(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_action_json(tmpdir, "a.json", [["WR_quit"]])
            _write_action_json(tmpdir, "b.json", [["WR_quit"]])
            fake_pool_cls = MagicMock()
            fake_pool = MagicMock()
            fake_pool_cls.return_value.__enter__.return_value = fake_pool
            fake_pool.map.return_value = [
                ("a.json", True, []),
                ("b.json", True, []),
            ]
            with patch(
                "je_web_runner.utils.cli.cli_main.ProcessPoolExecutor",
                fake_pool_cls,
            ):
                main(["-d", tmpdir, "--parallel", "2", "--parallel-mode", "process"])
                fake_pool.map.assert_called_once()

    def test_report_flag_invokes_all_generators(self):
        with patch("je_web_runner.utils.generate_report.generate_html_report.generate_html_report") as html_mock, \
                patch("je_web_runner.utils.generate_report.generate_json_report.generate_json_report") as json_mock, \
                patch("je_web_runner.utils.generate_report.generate_xml_report.generate_xml_report") as xml_mock, \
                patch(
                    "je_web_runner.utils.generate_report.generate_junit_xml_report.generate_junit_xml_report"
                ) as junit_mock:
            main(["--report", "demo"])
            html_mock.assert_called_once_with("demo")
            json_mock.assert_called_once_with("demo")
            xml_mock.assert_called_once_with("demo")
            junit_mock.assert_called_once_with("demo")


class TestParseExecuteStr(unittest.TestCase):

    def test_parses_plain_json(self):
        result = _parse_execute_str(json.dumps([["WR_quit"]]))
        self.assertEqual(result, [["WR_quit"]])


if __name__ == "__main__":
    unittest.main()
