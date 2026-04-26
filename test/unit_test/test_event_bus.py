import tempfile
import threading
import unittest
from pathlib import Path

from je_web_runner.utils.event_bus import (
    EventBus,
    EventBusError,
)


class TestEventBus(unittest.TestCase):

    def test_publish_and_poll(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "events.log"
            bus = EventBus(log_path=log, sender="shard-1")
            bus.publish("setup", {"step": 1})
            bus.publish("setup", {"step": 2})
            events = bus.poll()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].sender, "shard-1")

    def test_poll_offset_skips_old(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "events.log"
            bus = EventBus(log_path=log)
            bus.publish("topic", {"i": 1})
            offset = bus.current_offset()
            bus.publish("topic", {"i": 2})
            events = bus.poll(offset=offset)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].payload["i"], 2)

    def test_topic_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "events.log"
            bus = EventBus(log_path=log)
            bus.publish("a", {})
            bus.publish("b", {})
            bus.publish("a", {})
            self.assertEqual(len(bus.poll(topics=["a"])), 2)

    def test_invalid_topic_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(log_path=Path(tmpdir) / "events.log")
            with self.assertRaises(EventBusError):
                bus.publish("", {})

    def test_invalid_payload_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(log_path=Path(tmpdir) / "events.log")
            with self.assertRaises(EventBusError):
                bus.publish("x", "not a dict")  # type: ignore[arg-type]

    def test_concurrent_publishers_no_tearing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(log_path=Path(tmpdir) / "events.log")

            def burst(idx):
                for i in range(20):
                    bus.publish("burst", {"shard": idx, "i": i})

            threads = [threading.Thread(target=burst, args=(n,)) for n in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            events = bus.poll()
            self.assertEqual(len(events), 80)
            payloads = {(e.payload["shard"], e.payload["i"]) for e in events}
            self.assertEqual(len(payloads), 80)

    def test_wait_for(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(log_path=Path(tmpdir) / "events.log")

            def publisher():
                import time
                time.sleep(0.05)
                bus.publish("ready", {"ok": True})

            threading.Thread(target=publisher, daemon=True).start()
            envelope = bus.wait_for("ready", timeout=2.0, poll_interval=0.02)
            self.assertEqual(envelope.payload["ok"], True)

    def test_wait_for_timeout_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bus = EventBus(log_path=Path(tmpdir) / "events.log")
            with self.assertRaises(EventBusError):
                bus.wait_for("never", timeout=0.05, poll_interval=0.01)

    def test_corrupted_line_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "events.log"
            log.write_text("not json\n", encoding="utf-8")
            bus = EventBus(log_path=log)
            with self.assertRaises(EventBusError):
                bus.poll()


if __name__ == "__main__":
    unittest.main()
