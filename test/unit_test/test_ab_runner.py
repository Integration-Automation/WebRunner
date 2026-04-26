import unittest

from je_web_runner.utils.ab_run.ab_runner import diff_records, run_ab
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestDiffRecords(unittest.TestCase):

    def test_identical_passes_no_diff(self):
        records = [{"function_name": "step1", "program_exception": "None"}]
        result = diff_records(records, records)
        self.assertEqual(result["differences"], [])
        self.assertTrue(result["summary"]["length_match"])

    def test_status_diff_reported(self):
        a = [{"function_name": "step1", "program_exception": "None"}]
        b = [{"function_name": "step1", "program_exception": "ValueError(\"x\")"}]
        diff = diff_records(a, b)
        self.assertEqual(len(diff["differences"]), 1)
        self.assertEqual(diff["differences"][0]["a"]["status"], "passed")
        self.assertEqual(diff["differences"][0]["b"]["status"], "failed")

    def test_function_diff_reported(self):
        a = [{"function_name": "step1", "program_exception": "None"}]
        b = [{"function_name": "step2", "program_exception": "None"}]
        diff = diff_records(a, b)
        self.assertEqual(len(diff["differences"]), 1)

    def test_length_mismatch_summary(self):
        a = [{"function_name": "step1", "program_exception": "None"}]
        b = []
        diff = diff_records(a, b)
        self.assertFalse(diff["summary"]["length_match"])


class TestRunAB(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_runs_both_sides_with_setups(self):
        captured = []

        def setup_a():
            captured.append("setup_a")

        def setup_b():
            captured.append("setup_b")

        def fake_runner(action_data):  # noqa: ARG001 — runner signature
            record_action_to_list("step", None, None)

        result = run_ab([], setup_a=setup_a, setup_b=setup_b, runner=fake_runner)
        self.assertEqual(captured, ["setup_a", "setup_b"])
        self.assertEqual(len(result["records_a"]), 1)
        self.assertEqual(len(result["records_b"]), 1)
        self.assertEqual(result["diff"]["differences"], [])

    def test_diff_surfaces_when_b_fails(self):
        toggle = {"side": "a"}

        def fake_runner(action_data):  # noqa: ARG001
            if toggle["side"] == "a":
                record_action_to_list("step", None, None)
                toggle["side"] = "b"
            else:
                record_action_to_list("step", None, RuntimeError("boom"))

        result = run_ab([], runner=fake_runner)
        self.assertEqual(len(result["diff"]["differences"]), 1)
        self.assertEqual(result["diff"]["differences"][0]["b"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
