"""Unit tests for je_web_runner.utils.speech_api_assert."""
import unittest

from je_web_runner.utils.speech_api_assert.assertions import (
    INSTALL_SCRIPT,
    SpeechApiAssertError,
    Utterance,
    assert_lang,
    assert_no_speech,
    assert_spoke,
    assert_within_volume,
    parse_spoken,
)


class TestParse(unittest.TestCase):

    def test_basic(self):
        out = parse_spoken([{"text": "hi", "lang": "en-US"}])
        self.assertEqual(out[0].text, "hi")

    def test_script(self):
        self.assertIn("speechSynthesis", INSTALL_SCRIPT)
        self.assertIn("SpeechRecognition", INSTALL_SCRIPT)

    def test_bad_payload(self):
        with self.assertRaises(SpeechApiAssertError):
            parse_spoken("nope")

    def test_skip_non_dict(self):
        self.assertEqual(parse_spoken(["x"]), [])

    def test_zero_volume_and_pitch_preserved(self):
        # A muted utterance (volume 0) / lowest pitch (0) are valid values and
        # must not be coalesced to the 1.0 default.
        out = parse_spoken([{"text": "hi", "volume": 0, "pitch": 0}])
        self.assertEqual(out[0].volume, 0.0)
        self.assertEqual(out[0].pitch, 0.0)

    def test_missing_rate_defaults_to_one(self):
        out = parse_spoken([{"text": "hi"}])
        self.assertEqual(out[0].rate, 1.0)
        self.assertEqual(out[0].volume, 1.0)


class TestAssertSpoke(unittest.TestCase):

    def test_pass(self):
        u = assert_spoke([Utterance(text="Hello world")],
                         text_contains="Hello")
        self.assertEqual(u.text, "Hello world")

    def test_fail(self):
        with self.assertRaises(SpeechApiAssertError):
            assert_spoke([Utterance(text="x")], text_contains="y")

    def test_empty_needle(self):
        with self.assertRaises(SpeechApiAssertError):
            assert_spoke([Utterance(text="x")], text_contains="")


class TestLang(unittest.TestCase):

    def test_pass(self):
        assert_lang([Utterance(text="x", lang="ja-JP")],
                    expected_lang="ja-JP")

    def test_fail(self):
        with self.assertRaises(SpeechApiAssertError):
            assert_lang([Utterance(text="x", lang="en-US")],
                        expected_lang="ja-JP")

    def test_empty_expected(self):
        with self.assertRaises(SpeechApiAssertError):
            assert_lang([], expected_lang="")


class TestNoSpeech(unittest.TestCase):

    def test_pass(self):
        assert_no_speech([])

    def test_fail(self):
        with self.assertRaises(SpeechApiAssertError):
            assert_no_speech([Utterance(text="surprise!")])


class TestVolume(unittest.TestCase):

    def test_pass(self):
        assert_within_volume([Utterance(text="x", volume=0.5)],
                             min_volume=0.4, max_volume=0.8)

    def test_fail(self):
        with self.assertRaises(SpeechApiAssertError):
            assert_within_volume([Utterance(text="x", volume=0.1)],
                                 min_volume=0.4, max_volume=0.8)

    def test_bad_bounds(self):
        with self.assertRaises(SpeechApiAssertError):
            assert_within_volume([], min_volume=2, max_volume=0)


if __name__ == "__main__":
    unittest.main()
