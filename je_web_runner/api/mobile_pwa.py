"""Facade: Mobile and PWA: touch gestures, viewport, virtual keyboard, pull-to-refresh, real devices."""
from je_web_runner.utils.device_cloud.real_device import (
    DeviceCloudError, CloudCredentials, load_credentials, RealDeviceCaps, build_capabilities, CloudSession,
    connect_real_device, fetch_session_info, update_session_status, session_summary_markdown,
)
from je_web_runner.utils.pull_to_refresh.refresh import (
    PullToRefreshError, PullToRefreshSnapshot, parse_snapshot as pull_to_refresh_parse_snapshot,
    assert_overscroll_contained, assert_threshold_sensible, RefreshEvent, assert_refresh_triggered,
)
from je_web_runner.utils.touch_gesture.gesture import (
    TouchGestureError, Phase, TouchPoint, TouchFrame, tap, long_press, swipe, pinch, RecordedTouch,
    parse_touch_events, assert_received, assert_two_finger, gesture_distance_px,
)
from je_web_runner.utils.viewport_audit.audit import (
    ViewportAuditError, ViewportMeta, parse_meta, assert_meta_present, assert_responsive_width,
    assert_user_scalable_allowed, assert_notch_aware, SafeAreaSnapshot, parse_safe_area, assert_safe_area_padding,
)
from je_web_runner.utils.virtual_keyboard.keyboard import (
    VirtualKeyboardError, ViewportSnapshot, parse_snapshot as virtual_keyboard_parse_snapshot,
    assert_keyboard_shrunk, assert_keyboard_inset_set, FocusedElementBox, assert_focused_visible,
)

__all__ = [
    "DeviceCloudError", "CloudCredentials", "load_credentials", "RealDeviceCaps", "build_capabilities",
    "CloudSession", "connect_real_device", "fetch_session_info", "update_session_status",
    "session_summary_markdown", "PullToRefreshError", "PullToRefreshSnapshot", "pull_to_refresh_parse_snapshot",
    "assert_overscroll_contained", "assert_threshold_sensible", "RefreshEvent", "assert_refresh_triggered",
    "TouchGestureError", "Phase", "TouchPoint", "TouchFrame", "tap", "long_press", "swipe", "pinch",
    "RecordedTouch", "parse_touch_events", "assert_received", "assert_two_finger", "gesture_distance_px",
    "ViewportAuditError", "ViewportMeta", "parse_meta", "assert_meta_present", "assert_responsive_width",
    "assert_user_scalable_allowed", "assert_notch_aware", "SafeAreaSnapshot", "parse_safe_area",
    "assert_safe_area_padding", "VirtualKeyboardError", "ViewportSnapshot", "virtual_keyboard_parse_snapshot",
    "assert_keyboard_shrunk", "assert_keyboard_inset_set", "FocusedElementBox", "assert_focused_visible",
]
