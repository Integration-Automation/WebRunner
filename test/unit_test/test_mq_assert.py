"""Unit tests for je_web_runner.utils.mq_assert."""
import unittest

from je_web_runner.utils.mq_assert.assertions import (
    Message,
    MqAssertError,
    assert_idempotent,
    assert_message_published,
    assert_no_message,
    assert_ordered,
    drain_topic,
)


class FakeConsumer:
    def __init__(self, payload):
        self.payload = payload

    def drain(self, topic, *, timeout=5.0):
        return self.payload


class TestDrain(unittest.TestCase):

    def test_messages_pass_through(self):
        c = FakeConsumer([Message(topic="t", body={"x": 1})])
        out = drain_topic(c, "t")
        self.assertEqual(out[0].body["x"], 1)

    def test_dict_messages(self):
        c = FakeConsumer([{"body": {"x": 2}, "key": "k"}])
        out = drain_topic(c, "t")
        self.assertEqual(out[0].key, "k")
        self.assertEqual(out[0].topic, "t")

    def test_empty_topic(self):
        with self.assertRaises(MqAssertError):
            drain_topic(FakeConsumer([]), "")

    def test_bad_consumer(self):
        with self.assertRaises(MqAssertError):
            drain_topic(object(), "t")  # NOSONAR python:S5655 - deliberate bad input

    def test_non_seq_return(self):
        class C:
            def drain(self, topic, *, timeout=5.0):
                return "nope"
        with self.assertRaises(MqAssertError):
            drain_topic(C(), "t")

    def test_bad_message_shape(self):
        c = FakeConsumer([42])
        with self.assertRaises(MqAssertError):
            drain_topic(c, "t")


class TestAssertPublished(unittest.TestCase):

    def test_pass(self):
        msgs = [Message(topic="t", body={"event": "login"}, key="u1")]
        found = assert_message_published(msgs, body_contains={"event": "login"})
        self.assertEqual(found.key, "u1")

    def test_key_match(self):
        msgs = [Message(topic="t", body={}, key="u1")]
        assert_message_published(msgs, key_matches="u1")

    def test_header_match(self):
        msgs = [Message(topic="t", body={}, headers={"x": "y"})]
        assert_message_published(msgs, header_equals={"x": "y"})

    def test_json_string_body(self):
        msgs = [Message(topic="t", body='{"event": "login"}')]
        assert_message_published(msgs, body_contains={"event": "login"})

    def test_bytes_body(self):
        msgs = [Message(topic="t", body=b'{"event":"login"}')]
        assert_message_published(msgs, body_contains={"event": "login"})

    def test_fail(self):
        msgs = [Message(topic="t", body={"event": "logout"})]
        with self.assertRaises(MqAssertError):
            assert_message_published(msgs, body_contains={"event": "login"})

    def test_invalid_messages(self):
        with self.assertRaises(MqAssertError):
            assert_message_published("nope")


class TestAssertNo(unittest.TestCase):

    def test_pass(self):
        assert_no_message([Message(topic="other", body={})], topic="x")

    def test_fail(self):
        with self.assertRaises(MqAssertError):
            assert_no_message(
                [Message(topic="t", body={"pii": True})],
                topic="t", body_contains={"pii": True},
            )


class TestIdempotent(unittest.TestCase):

    def test_pass(self):
        assert_idempotent([Message(topic="t", body={}, key="a")], key="a")

    def test_fail(self):
        with self.assertRaises(MqAssertError):
            assert_idempotent([
                Message(topic="t", body={}, key="a"),
                Message(topic="t", body={}, key="a"),
            ], key="a")


class TestOrdered(unittest.TestCase):

    def test_pass(self):
        msgs = [
            Message(topic="t", body={"type": "created"}, key="x"),
            Message(topic="t", body={"type": "shipped"}, key="x"),
        ]
        assert_ordered(msgs, key="x", expected_order=["created", "shipped"])

    def test_fail(self):
        msgs = [
            Message(topic="t", body={"type": "shipped"}, key="x"),
            Message(topic="t", body={"type": "created"}, key="x"),
        ]
        with self.assertRaises(MqAssertError):
            assert_ordered(msgs, key="x",
                           expected_order=["created", "shipped"])


if __name__ == "__main__":
    unittest.main()
