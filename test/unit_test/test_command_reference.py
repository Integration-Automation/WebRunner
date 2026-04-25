import os
import tempfile
import unittest

from je_web_runner.utils.docs.command_reference import (
    build_command_reference,
    export_command_reference,
    list_commands,
)


class TestCommandReference(unittest.TestCase):

    def test_reference_lists_known_commands(self):
        markdown = build_command_reference()
        self.assertIn("WR_to_url", markdown)
        self.assertIn("WR_quit_all", markdown)
        self.assertIn("| Command | Signature | Summary |", markdown)

    def test_export_writes_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "reference.md")
            written = export_command_reference(target)
            self.assertTrue(os.path.exists(written))
            with open(written, encoding="utf-8") as ref_file:
                content = ref_file.read()
            self.assertIn("WR_to_url", content)

    def test_list_commands_only_returns_wr_prefixed(self):
        names = list_commands()
        self.assertTrue(all(name.startswith("WR_") for name in names))


if __name__ == "__main__":
    unittest.main()
