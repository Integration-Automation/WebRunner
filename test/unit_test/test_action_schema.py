import json
import os
import tempfile
import unittest

from je_web_runner.utils.schema.action_schema import build_action_schema, export_schema


class TestBuildSchema(unittest.TestCase):

    def test_schema_top_level_oneof(self):
        schema = build_action_schema()
        self.assertIn("oneOf", schema)
        self.assertEqual(len(schema["oneOf"]), 2)

    def test_action_definition_constrains_lengths_and_command_name(self):
        schema = build_action_schema()
        action_def = schema["definitions"]["action"]
        self.assertEqual(action_def["minItems"], 1)
        self.assertEqual(action_def["maxItems"], 3)
        first = action_def["prefixItems"][0]
        self.assertEqual(first["type"], "string")
        self.assertIn("WR_to_url", first["enum"])
        self.assertIn("WR_quit_all", first["enum"])
        # legacy aliases must still appear so existing files validate.
        self.assertIn("WR_SaveTestObject", first["enum"])

    def test_dict_form_requires_webdriver_wrapper(self):
        schema = build_action_schema()
        dict_form = next(option for option in schema["oneOf"]
                         if option.get("type") == "object")
        self.assertIn("webdriver_wrapper", dict_form["required"])
        self.assertIn("meta", dict_form["properties"])


class TestExportSchema(unittest.TestCase):

    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "schema.json")
            written = export_schema(target)
            self.assertTrue(os.path.exists(written))
            with open(written, encoding="utf-8") as schema_file:
                payload = json.load(schema_file)
            self.assertEqual(payload["$schema"],
                             "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
