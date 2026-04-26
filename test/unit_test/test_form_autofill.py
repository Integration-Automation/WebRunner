import unittest

from je_web_runner.utils.form_autofill import (
    FormAutoFillError,
    classify_field,
    match_fields,
    plan_fill_actions,
)


class TestClassifyField(unittest.TestCase):

    def test_password_type(self):
        self.assertEqual(classify_field({"type": "password"}), "password")

    def test_email_type(self):
        self.assertEqual(classify_field({"type": "email"}), "email")

    def test_search_type(self):
        self.assertEqual(classify_field({"type": "search"}), "search")

    def test_label_recognised(self):
        self.assertEqual(
            classify_field({"type": "text", "label": "First name"}),
            "first_name",
        )

    def test_placeholder_recognised(self):
        self.assertEqual(
            classify_field({"type": "text", "placeholder": "Postal Code"}),
            "zip",
        )

    def test_unrelated_field(self):
        self.assertIsNone(classify_field({"type": "text", "label": "Coupon"}))

    def test_data_testid_priority(self):
        self.assertEqual(
            classify_field({"type": "text", "data-testid": "username-input"}),
            "username",
        )


class TestMatchFields(unittest.TestCase):

    def test_match_by_exact_name(self):
        fields = [{"type": "text", "id": "fullname"}]
        fixture = {"fullname": "Alice"}
        matches = match_fields(fields, fixture)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].fixture_key, "fullname")
        self.assertEqual(matches[0].confidence, 1.0)

    def test_match_via_canonical(self):
        fields = [{"type": "email", "id": "user_email"}]
        fixture = {"email": "alice@example.com"}
        matches = match_fields(fields, fixture)
        self.assertEqual(matches[0].fixture_key, "email")

    def test_match_via_alias(self):
        fields = [{"type": "tel", "id": "main"}]
        fixture = {"phonenumber": "+1234567890"}
        matches = match_fields(fields, fixture)
        self.assertEqual(matches[0].fixture_key, "phonenumber")

    def test_no_match_skips_field(self):
        fields = [{"type": "text", "id": "coupon", "label": "Coupon code"}]
        fixture = {"email": "x@y.com"}
        self.assertEqual(match_fields(fields, fixture), [])

    def test_invalid_fixture_raises(self):
        with self.assertRaises(FormAutoFillError):
            match_fields([], "not a dict")  # type: ignore[arg-type]


class TestPlanFillActions(unittest.TestCase):

    def test_generates_action_triplet(self):
        fields = [
            {"type": "email", "id": "email", "label": "Email"},
            {"type": "password", "id": "pwd", "label": "Password"},
        ]
        fixture = {"email": "a@b.com", "password": "wonder"}  # nosec B106 — test fixture
        actions = plan_fill_actions(fields, fixture)
        commands = [a[0] for a in actions]
        # Three-step block per field: save_test_object, find, input
        self.assertEqual(commands.count("WR_save_test_object"), 2)
        self.assertEqual(commands.count("WR_element_input"), 2)
        self.assertIn("a@b.com", repr(actions))

    def test_submit_button_appended(self):
        fields = [{"type": "email", "id": "email"}]
        actions = plan_fill_actions(
            fields, {"email": "a@b.com"},
            submit_locator={"strategy": "ID", "value": "submit"},
        )
        commands = [a[0] for a in actions]
        self.assertEqual(commands[-1], "WR_element_click")

    def test_field_without_locator_skipped(self):
        fields = [{"type": "text", "label": "Name"}]
        actions = plan_fill_actions(fields, {"full_name": "x"})
        self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()
