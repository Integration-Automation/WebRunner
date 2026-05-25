"""Unit tests for je_web_runner.utils.touch_gesture."""
import unittest

from je_web_runner.utils.touch_gesture.gesture import (
    Phase,
    RecordedTouch,
    TouchFrame,
    TouchGestureError,
    TouchPoint,
    assert_received,
    assert_two_finger,
    gesture_distance_px,
    long_press,
    parse_touch_events,
    pinch,
    swipe,
    tap,
)


class TestTap(unittest.TestCase):

    def test_pass(self):
        frames = tap(10, 20)
        self.assertEqual(frames[0].type, Phase.START)
        self.assertEqual(frames[-1].type, Phase.END)

    def test_bad_coord(self):
        with self.assertRaises(TouchGestureError):
            tap("x", 0)


class TestLongPress(unittest.TestCase):

    def test_pass(self):
        frames = long_press(10, 20, hold_ms=800)
        self.assertEqual(len(frames), 3)

    def test_bad_hold(self):
        with self.assertRaises(TouchGestureError):
            long_press(10, 20, hold_ms=100)


class TestSwipe(unittest.TestCase):

    def test_pass(self):
        frames = swipe((0, 0), (100, 0), steps=4)
        self.assertEqual(frames[0].type, Phase.START)
        # 1 start + 3 moves + 1 end
        self.assertEqual(len(frames), 5)

    def test_bad_steps(self):
        with self.assertRaises(TouchGestureError):
            swipe((0, 0), (1, 0), steps=1)

    def test_distance(self):
        d = gesture_distance_px(swipe((0, 0), (100, 0), steps=10))
        self.assertAlmostEqual(d, 90.0, delta=5)


class TestPinch(unittest.TestCase):

    def test_pass(self):
        frames = pinch((100, 100), start_radius=20, end_radius=80, steps=4)
        self.assertEqual(len(frames[0].points), 2)

    def test_bad_radius(self):
        with self.assertRaises(TouchGestureError):
            pinch((0, 0), start_radius=-1, end_radius=10)

    def test_bad_steps(self):
        with self.assertRaises(TouchGestureError):
            pinch((0, 0), start_radius=10, end_radius=20, steps=1)


class TestCdpFormat(unittest.TestCase):

    def test_to_cdp(self):
        frame = TouchFrame(type=Phase.START, points=[TouchPoint(x=10, y=20)])
        cdp = frame.to_cdp()
        self.assertEqual(cdp["type"], "touchStart")
        self.assertEqual(cdp["touchPoints"][0]["x"], 10)


class TestParseEvents(unittest.TestCase):

    def test_basic(self):
        events = parse_touch_events([{"type": "touchstart", "touchCount": 1}])
        self.assertEqual(events[0].type, "touchstart")

    def test_bad(self):
        with self.assertRaises(TouchGestureError):
            parse_touch_events("nope")

    def test_skip_non_dict(self):
        self.assertEqual(parse_touch_events(["x"]), [])


class TestAssert(unittest.TestCase):

    def test_received_pass(self):
        assert_received([RecordedTouch(type="touchstart")], type="touchstart")

    def test_received_fail(self):
        with self.assertRaises(TouchGestureError):
            assert_received([], type="touchstart")

    def test_two_finger_pass(self):
        assert_two_finger([RecordedTouch(type="touchstart", touch_count=2)])

    def test_two_finger_fail(self):
        with self.assertRaises(TouchGestureError):
            assert_two_finger([RecordedTouch(type="touchstart", touch_count=1)])


if __name__ == "__main__":
    unittest.main()
