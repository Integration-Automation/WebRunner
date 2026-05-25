"""Unit tests for je_web_runner.utils.pip_assert."""
import unittest

from je_web_runner.utils.pip_assert.pip import (
    INSTALL_SCRIPT,
    Mode,
    PipAssertError,
    PipEvent,
    PipLog,
    assert_entered,
    assert_exited_cleanly,
    assert_size_at_least,
    parse_log,
)


class TestScript(unittest.TestCase):

    def test_contains(self):
        self.assertIn("requestPictureInPicture", INSTALL_SCRIPT)


class TestParse(unittest.TestCase):

    def test_basic(self):
        log = parse_log([{"kind": "enter", "mode": "video"}])
        self.assertEqual(log.events[0].mode, Mode.VIDEO)

    def test_document(self):
        log = parse_log([{"kind": "enter", "mode": "document",
                          "width": 400, "height": 300}])
        self.assertEqual(log.events[0].width, 400)

    def test_bad_mode(self):
        with self.assertRaises(PipAssertError):
            parse_log([{"kind": "enter", "mode": "weird"}])

    def test_skip_bad_kind(self):
        log = parse_log([{"kind": "weird", "mode": "video"}])
        self.assertEqual(len(log.events), 0)

    def test_bad_payload(self):
        with self.assertRaises(PipAssertError):
            parse_log("nope")


class TestEntered(unittest.TestCase):

    def test_pass(self):
        assert_entered(PipLog(events=[PipEvent(kind="enter", mode=Mode.VIDEO)]))

    def test_fail(self):
        with self.assertRaises(PipAssertError):
            assert_entered(PipLog())

    def test_doc(self):
        assert_entered(PipLog(events=[
            PipEvent(kind="enter", mode=Mode.DOCUMENT),
        ]), mode=Mode.DOCUMENT)


class TestExited(unittest.TestCase):

    def test_pass(self):
        assert_exited_cleanly(PipLog(events=[
            PipEvent(kind="enter", mode=Mode.VIDEO),
            PipEvent(kind="exit", mode=Mode.VIDEO),
        ]))

    def test_dangling(self):
        with self.assertRaises(PipAssertError):
            assert_exited_cleanly(PipLog(events=[
                PipEvent(kind="enter", mode=Mode.VIDEO),
            ]))


class TestSize(unittest.TestCase):

    def test_pass(self):
        assert_size_at_least(
            PipLog(events=[PipEvent(kind="enter", mode=Mode.DOCUMENT,
                                    width=400, height=300)]),
            min_width=300, min_height=200,
        )

    def test_fail(self):
        with self.assertRaises(PipAssertError):
            assert_size_at_least(
                PipLog(events=[PipEvent(kind="enter", mode=Mode.DOCUMENT,
                                        width=100, height=100)]),
                min_width=300, min_height=200,
            )

    def test_bad_min(self):
        with self.assertRaises(PipAssertError):
            assert_size_at_least(PipLog(), min_width=0, min_height=0)


if __name__ == "__main__":
    unittest.main()
