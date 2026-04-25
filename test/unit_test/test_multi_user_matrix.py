import unittest

from je_web_runner.utils.multi_user.matrix import MultiUserError, run_for_users
from je_web_runner.utils.test_record.test_record_class import (
    record_action_to_list,
    test_record_instance,
)


class TestRunForUsers(unittest.TestCase):

    def setUp(self):
        test_record_instance.clean_record()
        self._original = test_record_instance.init_record
        test_record_instance.init_record = True

    def tearDown(self):
        test_record_instance.clean_record()
        test_record_instance.init_record = self._original

    def test_empty_user_list_raises(self):
        with self.assertRaises(MultiUserError):
            run_for_users([], [])

    def test_returns_per_user_records(self):
        captured = []

        def fake_runner(action_data):  # noqa: ARG001
            record_action_to_list("step", None, None)
            captured.append(1)

        result = run_for_users(
            [],
            [
                ("alice", lambda: None),
                ("bob", None),
            ],
            runner=fake_runner,
        )
        self.assertIn("alice", result["by_user"])
        self.assertIn("bob", result["by_user"])
        self.assertEqual(len(captured), 2)
        self.assertEqual(result["diff"], [])

    def test_diff_emits_when_status_differs(self):
        toggle = {"side": "alice"}

        def fake_runner(action_data):  # noqa: ARG001
            if toggle["side"] == "alice":
                record_action_to_list("step", None, None)
                toggle["side"] = "bob"
            else:
                record_action_to_list("step", None, RuntimeError("boom"))

        result = run_for_users(
            [],
            [("alice", None), ("bob", None)],
            runner=fake_runner,
        )
        self.assertEqual(len(result["diff"]), 1)
        self.assertEqual(result["diff"][0]["status"], {"alice": "passed", "bob": "failed"})

    def test_diff_emits_when_step_count_differs(self):
        toggle = {"side": "alice"}

        def fake_runner(action_data):  # noqa: ARG001
            if toggle["side"] == "alice":
                record_action_to_list("step", None, None)
                record_action_to_list("only_alice", None, None)
                toggle["side"] = "bob"
            else:
                record_action_to_list("step", None, None)

        result = run_for_users(
            [],
            [("alice", None), ("bob", None)],
            runner=fake_runner,
        )
        # The second step exists for alice but not bob — diff[0] should fire.
        self.assertGreaterEqual(len(result["diff"]), 1)


if __name__ == "__main__":
    unittest.main()
