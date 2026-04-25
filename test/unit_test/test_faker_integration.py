import sys
import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.test_data.faker_integration import (
    FakerError,
    fake_email,
    fake_value,
    reset_faker,
    seed_faker,
)


class TestFakerSoftDependency(unittest.TestCase):

    def setUp(self):
        reset_faker()

    def tearDown(self):
        reset_faker()

    def test_missing_faker_raises_with_install_hint(self):
        with patch.dict(sys.modules, {"faker": None}):
            with self.assertRaises(FakerError) as ctx:
                fake_email()
            self.assertIn("pip install faker", str(ctx.exception))


class TestFakerHelpers(unittest.TestCase):

    def setUp(self):
        reset_faker()

    def tearDown(self):
        reset_faker()

    def test_seed_makes_output_deterministic(self):
        seed_faker(42)
        first = fake_email()
        reset_faker()
        seed_faker(42)
        self.assertEqual(first, fake_email())

    def test_fake_value_dispatches_to_provider(self):
        result = fake_value("color_name")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_unknown_provider_raises(self):
        with self.assertRaises(FakerError):
            fake_value("definitely_not_a_provider_xqz")


if __name__ == "__main__":
    unittest.main()
