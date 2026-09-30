"""Facade: Web-platform API assertions and mocks: storage, workers, media, devices, payments."""
from je_web_runner.utils.background_sync_assert.sync import (
    BackgroundSyncAssertError, SyncFire, SyncLog, parse_log as background_sync_assert_parse_log,
    assert_registered as background_sync_assert_assert_registered, assert_fired, assert_retry_happened,
    assert_no_quota_exhaustion,
)
from je_web_runner.utils.compression_streams.streams import (
    CompressionStreamsError, Algorithm, decompress, assert_round_trip, compression_ratio, assert_ratio_under,
)
from je_web_runner.utils.compute_pressure.pressure import (
    ComputePressureError, PressureLevel, PressureReaction, PressureLog, parse_log as compute_pressure_parse_log,
    assert_reaction_to, assert_throttled_at_or_above, assert_observer_disconnected,
)
from je_web_runner.utils.cookie_store_api.store import (
    CookieStoreApiError, CookieRecord, ChangeEvent, install_change_listener_script, parse_cookies,
    parse_change_events, assert_cookie_present, assert_cookie_absent, assert_change_for, assert_secure_only,
)
from je_web_runner.utils.credential_management.credentials import (
    CredentialManagementError, SeedCredential, build_seed, StoredCall, CmLog,
    parse_log as credential_management_parse_log, assert_stored, assert_no_password_in_clear,
    assert_prevent_silent_access_called, assert_get_requested_mediation,
)
from je_web_runner.utils.cross_tab_sync.sync_assertions import (
    CrossTabSyncError, set_storage_value, get_storage_value, wait_for_storage, install_broadcast_recorder,
    broadcast_message, collect_broadcast_messages, wait_for_broadcast, PropagationResult, assert_state_propagates,
    post_message_to_page,
)
from je_web_runner.utils.file_system_access.mock import (
    FileSystemAccessError, MockFile, WriteEvent, build_install_script as file_system_access_build_install_script,
    parse_writes, assert_no_writes, assert_wrote, combined_payload,
)
from je_web_runner.utils.indexed_db_explorer.explorer import (
    IndexedDbExplorerError, build_harvest_script, StoreSnapshot, IdbSnapshot, assert_db_exists,
    assert_store_present, assert_record_count, assert_key_present, assert_record_matching, assert_index_present,
    SnapshotDiff, diff_snapshots,
)
from je_web_runner.utils.notifications_audit.audit import (
    NotificationsAuditError, PermissionResult, PermissionRequest, NotificationShown, NotificationsLog,
    build_install_script as notifications_audit_build_install_script, parse_log as notifications_audit_parse_log,
    assert_no_prompt_without_gesture, assert_no_prompt_before, assert_no_spam_after_deny,
    assert_notification_shown as notifications_audit_assert_notification_shown, assert_unique_tags,
)
from je_web_runner.utils.payment_request_assert.payment import (
    PaymentRequestAssertError, ConstructedPaymentRequest, CompletedPayment, PaymentLog,
    parse_log as payment_request_assert_parse_log, assert_supports, assert_total_currency, assert_completed,
    assert_shipping_required,
)
from je_web_runner.utils.pip_assert.pip import (
    PipAssertError, Mode, PipEvent, PipLog, parse_log as pip_assert_parse_log, assert_entered,
    assert_exited_cleanly, assert_size_at_least,
)
from je_web_runner.utils.popover_assert.popover import (
    PopoverAssertError, PopoverKind, PopoverState, parse_snapshot as popover_assert_parse_snapshot, assert_open,
    assert_closed, assert_only_one_modal, assert_invoker_link, assert_no_open,
)
from je_web_runner.utils.service_worker.sw_control import (
    ServiceWorkerError, selenium_unregister_service_workers, selenium_clear_caches, selenium_bypass_service_worker,
    playwright_unregister_service_workers, playwright_clear_caches, playwright_bypass_service_worker,
)
from je_web_runner.utils.speculation_rules.rules import (
    SpeculationRulesError, RuleKind, SpeculationRule, build_script_tag, PrerenderLog,
    parse_log as speculation_rules_parse_log, assert_activated, assert_no_double_fire, assert_fire_count,
)
from je_web_runner.utils.speech_api_assert.assertions import (
    SpeechApiAssertError, Utterance, parse_spoken, assert_spoke, assert_lang, assert_no_speech,
    assert_within_volume,
)
from je_web_runner.utils.sse_assert.stream import (
    SseAssertError, SseEvent, parse_sse_stream, SseRecorder, assert_event_count, assert_received_event,
    assert_data_contains, assert_json_shape as sse_assert_assert_json_shape, assert_strictly_increasing_ids,
    to_json as sse_assert_to_json,
)
from je_web_runner.utils.storage.browser_storage import (
    StorageError, selenium_local_storage_set, selenium_local_storage_get, selenium_local_storage_remove,
    selenium_local_storage_clear, selenium_local_storage_all, selenium_session_storage_set,
    selenium_session_storage_get, selenium_session_storage_clear, selenium_indexed_db_drop,
    playwright_local_storage_set, playwright_local_storage_get, playwright_local_storage_remove,
    playwright_local_storage_clear, playwright_local_storage_all, playwright_session_storage_set,
    playwright_session_storage_get, playwright_session_storage_clear, playwright_indexed_db_drop,
)
from je_web_runner.utils.storage_buckets.buckets import (
    StorageBucketsError, BucketSnapshot, BucketsReport, parse_snapshot as storage_buckets_parse_snapshot,
    assert_supported, assert_bucket_present, assert_idb_isolated, assert_durability, assert_no_unexpected_buckets,
)
from je_web_runner.utils.three_d_secure_flow.flow import (
    ThreeDSecureFlowError, TransStatus, Outcome, Flow, classify, assert_outcome, assert_no_silent_finalize,
    assert_challenge_branch_complete, assert_user_message_for,
)
from je_web_runner.utils.time_freezer.freezer import (
    TimeFreezerError, to_epoch_ms, FreezeConfig, build_freezer_script, attach_to_cdp, freeze_at, slow_motion,
)
from je_web_runner.utils.view_transitions.transitions import (
    ViewTransitionsError, build_instrumentation_script, TransitionRun, parse_log as view_transitions_parse_log,
    assert_all_finished, assert_under_duration, assert_cls_under, assert_group_present,
)
from je_web_runner.utils.wake_lock_assert.lock import (
    WakeLockAssertError, WakeLockEvent, WakeLockLog, parse_log as wake_lock_assert_parse_log, assert_acquired,
    assert_no_leak, assert_released_by_app, assert_re_acquired_after_visibility,
)
from je_web_runner.utils.web_locks.locks import (
    WebLocksError, LockOutcome, LockEvent, parse_log as web_locks_parse_log, assert_no_deadlock, assert_serialised,
    assert_if_available_unavailable, assert_acquired_count,
)
from je_web_runner.utils.web_push_assert.push import (
    WebPushAssertError, Subscription, Notification, PushLog, parse_log as web_push_assert_parse_log,
    assert_subscribed_with_vapid, assert_user_visible_only, assert_endpoint_recognised,
    assert_notification_shown as web_push_assert_assert_notification_shown,
)
from je_web_runner.utils.web_share_assert.share import (
    WebShareAssertError, ShareCall, FallbackEvent, ShareLog, parse_log as web_share_assert_parse_log,
    assert_shared, assert_url_origin, assert_has_field, assert_fallback_shown,
)
from je_web_runner.utils.webauthn_mock.mock import (
    WebauthnMockError, MockCredential, build_credential, CeremonyLog, parse_log as webauthn_mock_parse_log,
    assert_registered as webauthn_mock_assert_registered, assert_signed_in, assert_user_verification,
)
from je_web_runner.utils.webcodecs_assert.assertions import (
    WebcodecsAssertError, ChunkType, EncodedChunk, parse_chunks, assert_codec, assert_resolution,
    assert_keyframe_interval, estimate_framerate, assert_framerate_at_least,
)
from je_web_runner.utils.webgpu_pixel_verify.pixel import (
    WebgpuPixelVerifyError, CanvasFrame, parse_frame, mean_rgba, assert_mean_in_band, assert_no_fully_transparent,
    assert_no_solid_color, tile_diff_score, assert_similar,
)
from je_web_runner.utils.webhid_mock.mock import (
    WebhidMockError, MockDevice, build_mock_device as webhid_mock_build_mock_device, build_input_report,
    OutgoingReport, parse_outgoing as webhid_mock_parse_outgoing, assert_output_reports,
)
from je_web_runner.utils.webrtc_assert.peer import (
    WebRtcAssertError, ConnectionState, IceState, SignalingState, TrackInfo, PeerSnapshot, RtpStats,
    aggregate_stats, assert_connected, assert_track_present, assert_sdp_has_codec, assert_no_packet_loss,
    assert_min_bytes_flowed, export_snapshot,
)
from je_web_runner.utils.webserial_mock.mock import (
    WebserialMockError, MockSerialPort, build_mock_port, encode_lines, parse_outbound, assert_lines_written,
)
from je_web_runner.utils.websocket_assert.frames import (
    WebSocketAssertError, WsFrame, WsFrameRecorder, assert_frame_count, assert_frame_received,
    assert_payload_contains as websocket_assert_assert_payload_contains,
    assert_json_shape as websocket_assert_assert_json_shape, assert_pubsub_pattern,
    to_json as websocket_assert_to_json,
)
from je_web_runner.utils.webtransport_assert.streams import (
    WebTransportAssertError, WtFrame, WtFrameRecorder, assert_datagram_count, assert_stream_complete,
    assert_payload_contains as webtransport_assert_assert_payload_contains,
    assert_json_shape as webtransport_assert_assert_json_shape, to_json as webtransport_assert_to_json,
)
from je_web_runner.utils.webusb_mock.mock import (
    WebusbMockError, MockUsbDevice, build_mock_device as webusb_mock_build_mock_device, OutgoingCall,
    parse_outgoing as webusb_mock_parse_outgoing, assert_transfer_out, assert_control_out,
)

__all__ = [
    "BackgroundSyncAssertError", "SyncFire", "SyncLog", "background_sync_assert_parse_log",
    "background_sync_assert_assert_registered", "assert_fired", "assert_retry_happened",
    "assert_no_quota_exhaustion", "CompressionStreamsError", "Algorithm", "decompress", "assert_round_trip",
    "compression_ratio", "assert_ratio_under", "ComputePressureError", "PressureLevel", "PressureReaction",
    "PressureLog", "compute_pressure_parse_log", "assert_reaction_to", "assert_throttled_at_or_above",
    "assert_observer_disconnected", "CookieStoreApiError", "CookieRecord", "ChangeEvent",
    "install_change_listener_script", "parse_cookies", "parse_change_events", "assert_cookie_present",
    "assert_cookie_absent", "assert_change_for", "assert_secure_only", "CredentialManagementError",
    "SeedCredential", "build_seed", "StoredCall", "CmLog", "credential_management_parse_log", "assert_stored",
    "assert_no_password_in_clear", "assert_prevent_silent_access_called", "assert_get_requested_mediation",
    "CrossTabSyncError", "set_storage_value", "get_storage_value", "wait_for_storage",
    "install_broadcast_recorder", "broadcast_message", "collect_broadcast_messages", "wait_for_broadcast",
    "PropagationResult", "assert_state_propagates", "post_message_to_page", "FileSystemAccessError", "MockFile",
    "WriteEvent", "file_system_access_build_install_script", "parse_writes", "assert_no_writes", "assert_wrote",
    "combined_payload", "IndexedDbExplorerError", "build_harvest_script", "StoreSnapshot", "IdbSnapshot",
    "assert_db_exists", "assert_store_present", "assert_record_count", "assert_key_present",
    "assert_record_matching", "assert_index_present", "SnapshotDiff", "diff_snapshots", "NotificationsAuditError",
    "PermissionResult", "PermissionRequest", "NotificationShown", "NotificationsLog",
    "notifications_audit_build_install_script", "notifications_audit_parse_log",
    "assert_no_prompt_without_gesture", "assert_no_prompt_before", "assert_no_spam_after_deny",
    "notifications_audit_assert_notification_shown", "assert_unique_tags", "PaymentRequestAssertError",
    "ConstructedPaymentRequest", "CompletedPayment", "PaymentLog", "payment_request_assert_parse_log",
    "assert_supports", "assert_total_currency", "assert_completed", "assert_shipping_required", "PipAssertError",
    "Mode", "PipEvent", "PipLog", "pip_assert_parse_log", "assert_entered", "assert_exited_cleanly",
    "assert_size_at_least", "PopoverAssertError", "PopoverKind", "PopoverState", "popover_assert_parse_snapshot",
    "assert_open", "assert_closed", "assert_only_one_modal", "assert_invoker_link", "assert_no_open",
    "ServiceWorkerError", "selenium_unregister_service_workers", "selenium_clear_caches",
    "selenium_bypass_service_worker", "playwright_unregister_service_workers", "playwright_clear_caches",
    "playwright_bypass_service_worker", "SpeculationRulesError", "RuleKind", "SpeculationRule", "build_script_tag",
    "PrerenderLog", "speculation_rules_parse_log", "assert_activated", "assert_no_double_fire",
    "assert_fire_count", "SpeechApiAssertError", "Utterance", "parse_spoken", "assert_spoke", "assert_lang",
    "assert_no_speech", "assert_within_volume", "SseAssertError", "SseEvent", "parse_sse_stream", "SseRecorder",
    "assert_event_count", "assert_received_event", "assert_data_contains", "sse_assert_assert_json_shape",
    "assert_strictly_increasing_ids", "sse_assert_to_json", "StorageError", "selenium_local_storage_set",
    "selenium_local_storage_get", "selenium_local_storage_remove", "selenium_local_storage_clear",
    "selenium_local_storage_all", "selenium_session_storage_set", "selenium_session_storage_get",
    "selenium_session_storage_clear", "selenium_indexed_db_drop", "playwright_local_storage_set",
    "playwright_local_storage_get", "playwright_local_storage_remove", "playwright_local_storage_clear",
    "playwright_local_storage_all", "playwright_session_storage_set", "playwright_session_storage_get",
    "playwright_session_storage_clear", "playwright_indexed_db_drop", "StorageBucketsError", "BucketSnapshot",
    "BucketsReport", "storage_buckets_parse_snapshot", "assert_supported", "assert_bucket_present",
    "assert_idb_isolated", "assert_durability", "assert_no_unexpected_buckets", "ThreeDSecureFlowError",
    "TransStatus", "Outcome", "Flow", "classify", "assert_outcome", "assert_no_silent_finalize",
    "assert_challenge_branch_complete", "assert_user_message_for", "TimeFreezerError", "to_epoch_ms",
    "FreezeConfig", "build_freezer_script", "attach_to_cdp", "freeze_at", "slow_motion", "ViewTransitionsError",
    "build_instrumentation_script", "TransitionRun", "view_transitions_parse_log", "assert_all_finished",
    "assert_under_duration", "assert_cls_under", "assert_group_present", "WakeLockAssertError", "WakeLockEvent",
    "WakeLockLog", "wake_lock_assert_parse_log", "assert_acquired", "assert_no_leak", "assert_released_by_app",
    "assert_re_acquired_after_visibility", "WebLocksError", "LockOutcome", "LockEvent", "web_locks_parse_log",
    "assert_no_deadlock", "assert_serialised", "assert_if_available_unavailable", "assert_acquired_count",
    "WebPushAssertError", "Subscription", "Notification", "PushLog", "web_push_assert_parse_log",
    "assert_subscribed_with_vapid", "assert_user_visible_only", "assert_endpoint_recognised",
    "web_push_assert_assert_notification_shown", "WebShareAssertError", "ShareCall", "FallbackEvent", "ShareLog",
    "web_share_assert_parse_log", "assert_shared", "assert_url_origin", "assert_has_field",
    "assert_fallback_shown", "WebauthnMockError", "MockCredential", "build_credential", "CeremonyLog",
    "webauthn_mock_parse_log", "webauthn_mock_assert_registered", "assert_signed_in", "assert_user_verification",
    "WebcodecsAssertError", "ChunkType", "EncodedChunk", "parse_chunks", "assert_codec", "assert_resolution",
    "assert_keyframe_interval", "estimate_framerate", "assert_framerate_at_least", "WebgpuPixelVerifyError",
    "CanvasFrame", "parse_frame", "mean_rgba", "assert_mean_in_band", "assert_no_fully_transparent",
    "assert_no_solid_color", "tile_diff_score", "assert_similar", "WebhidMockError", "MockDevice",
    "webhid_mock_build_mock_device", "build_input_report", "OutgoingReport", "webhid_mock_parse_outgoing",
    "assert_output_reports", "WebRtcAssertError", "ConnectionState", "IceState", "SignalingState", "TrackInfo",
    "PeerSnapshot", "RtpStats", "aggregate_stats", "assert_connected", "assert_track_present",
    "assert_sdp_has_codec", "assert_no_packet_loss", "assert_min_bytes_flowed", "export_snapshot",
    "WebserialMockError", "MockSerialPort", "build_mock_port", "encode_lines", "parse_outbound",
    "assert_lines_written", "WebSocketAssertError", "WsFrame", "WsFrameRecorder", "assert_frame_count",
    "assert_frame_received", "websocket_assert_assert_payload_contains", "websocket_assert_assert_json_shape",
    "assert_pubsub_pattern", "websocket_assert_to_json", "WebTransportAssertError", "WtFrame", "WtFrameRecorder",
    "assert_datagram_count", "assert_stream_complete", "webtransport_assert_assert_payload_contains",
    "webtransport_assert_assert_json_shape", "webtransport_assert_to_json", "WebusbMockError", "MockUsbDevice",
    "webusb_mock_build_mock_device", "OutgoingCall", "webusb_mock_parse_outgoing", "assert_transfer_out",
    "assert_control_out",
]
