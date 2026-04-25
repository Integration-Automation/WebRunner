import unittest
from unittest.mock import MagicMock, patch

from je_web_runner.utils.testcontainers_integration.containers import (
    TestcontainersError,
    cleanup_all,
    start_postgres,
    start_redis,
    started_count,
    stop_container,
)


class TestTestcontainers(unittest.TestCase):

    def tearDown(self):
        cleanup_all()

    def test_start_postgres_invokes_module(self):
        fake_container = MagicMock()
        fake_class = MagicMock(return_value=fake_container)
        with patch(
            "je_web_runner.utils.testcontainers_integration.containers._require",
            return_value=fake_class,
        ):
            container = start_postgres(image="postgres:16-alpine", user="u", password="p", dbname="d")
            self.assertIs(container, fake_container)
            fake_class.assert_called_once_with(
                "postgres:16-alpine", user="u", password="p", dbname="d",
            )
            fake_container.start.assert_called_once()
            self.assertEqual(started_count(), 1)

    def test_stop_container_removes_from_tracking(self):
        fake_container = MagicMock()
        fake_class = MagicMock(return_value=fake_container)
        with patch(
            "je_web_runner.utils.testcontainers_integration.containers._require",
            return_value=fake_class,
        ):
            container = start_redis()
            self.assertEqual(started_count(), 1)
            stop_container(container)
            self.assertEqual(started_count(), 0)
            fake_container.stop.assert_called_once()

    def test_cleanup_all_stops_every_container(self):
        fake_class = MagicMock()
        fake_class.side_effect = lambda *a, **kw: MagicMock()
        with patch(
            "je_web_runner.utils.testcontainers_integration.containers._require",
            return_value=fake_class,
        ):
            start_postgres()
            start_redis()
            self.assertEqual(started_count(), 2)
            cleanup_all()
            self.assertEqual(started_count(), 0)

    def test_missing_testcontainers_raises_install_hint(self):
        # _require itself does the import; force it to fail.
        with patch(
            "je_web_runner.utils.testcontainers_integration.containers._require",
            side_effect=TestcontainersError("testcontainers is not installed."),
        ):
            with self.assertRaises(TestcontainersError):
                start_postgres()


if __name__ == "__main__":
    unittest.main()
