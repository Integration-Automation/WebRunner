"""Unit tests for je_web_runner.utils.webrtc_assert."""
import unittest

from je_web_runner.utils.webrtc_assert.peer import (
    ConnectionState,
    IceState,
    PeerSnapshot,
    RtpStats,
    SignalingState,
    TrackInfo,
    WebRtcAssertError,
    aggregate_stats,
    assert_connected,
    assert_min_bytes_flowed,
    assert_no_packet_loss,
    assert_sdp_has_codec,
    assert_track_present,
    export_snapshot,
)


def _connected_snapshot(**overrides):
    base = {
        "connection_state": ConnectionState.CONNECTED,
        "ice_connection_state": IceState.CONNECTED,
        "signaling_state": SignalingState.STABLE,
        "local_sdp": "m=audio 9 UDP/TLS/RTP/SAVPF 111\na=rtpmap:111 opus/48000/2",
        "remote_sdp": "m=video 9 UDP/TLS/RTP/SAVPF 96\na=rtpmap:96 VP8/90000",
        "remote_tracks": [TrackInfo(kind="audio"), TrackInfo(kind="video")],
        "local_tracks": [TrackInfo(kind="audio")],
    }
    base.update(overrides)
    return PeerSnapshot(**base)


class TestFromDict(unittest.TestCase):

    def test_minimal(self):
        snap = PeerSnapshot.from_dict({
            "connectionState": "connected",
            "iceConnectionState": "completed",
        })
        self.assertEqual(snap.connection_state, ConnectionState.CONNECTED)
        self.assertEqual(snap.ice_connection_state, IceState.COMPLETED)

    def test_with_tracks(self):
        snap = PeerSnapshot.from_dict({
            "connectionState": "connected",
            "iceConnectionState": "connected",
            "remoteTracks": [{"kind": "audio", "readyState": "live"}],
        })
        self.assertEqual(len(snap.remote_tracks), 1)

    def test_unknown_state_rejected(self):
        with self.assertRaises(WebRtcAssertError):
            PeerSnapshot.from_dict({"connectionState": "weird"})

    def test_rejects_non_dict(self):
        with self.assertRaises(WebRtcAssertError):
            PeerSnapshot.from_dict("not a dict")  # type: ignore[arg-type]


class TestAssertConnected(unittest.TestCase):

    def test_passes(self):
        assert_connected(_connected_snapshot())

    def test_fails_when_not_connected(self):
        with self.assertRaises(WebRtcAssertError):
            assert_connected(_connected_snapshot(
                connection_state=ConnectionState.FAILED,
            ))

    def test_fails_when_ice_disconnected(self):
        with self.assertRaises(WebRtcAssertError):
            assert_connected(_connected_snapshot(
                ice_connection_state=IceState.DISCONNECTED,
            ))

    def test_accepts_ice_completed(self):
        assert_connected(_connected_snapshot(
            ice_connection_state=IceState.COMPLETED,
        ))

    def test_rejects_non_snapshot(self):
        with self.assertRaises(WebRtcAssertError):
            assert_connected("not snap")  # type: ignore[arg-type]


class TestTrackPresent(unittest.TestCase):

    def test_remote_audio_present(self):
        track = assert_track_present(_connected_snapshot(), "audio")
        self.assertEqual(track.kind, "audio")

    def test_local_side(self):
        track = assert_track_present(_connected_snapshot(), "audio", side="local")
        self.assertEqual(track.kind, "audio")

    def test_missing_kind(self):
        with self.assertRaises(WebRtcAssertError):
            assert_track_present(_connected_snapshot(), "data")

    def test_ended_track_skipped(self):
        snap = _connected_snapshot(
            remote_tracks=[TrackInfo(kind="audio", ready_state="ended")],
        )
        with self.assertRaises(WebRtcAssertError):
            assert_track_present(snap, "audio")

    def test_invalid_side(self):
        with self.assertRaises(WebRtcAssertError):
            assert_track_present(_connected_snapshot(), "audio", side="weird")


class TestSdpCodec(unittest.TestCase):

    def test_local_codec_match(self):
        assert_sdp_has_codec(_connected_snapshot(), "opus")

    def test_remote_codec_match(self):
        assert_sdp_has_codec(_connected_snapshot(), "VP8", side="remote")

    def test_missing(self):
        with self.assertRaises(WebRtcAssertError):
            assert_sdp_has_codec(_connected_snapshot(), "h264")

    def test_empty_sdp(self):
        with self.assertRaises(WebRtcAssertError):
            assert_sdp_has_codec(_connected_snapshot(local_sdp=""), "opus")

    def test_empty_codec_name(self):
        with self.assertRaises(WebRtcAssertError):
            assert_sdp_has_codec(_connected_snapshot(), "")


class TestAggregateStats(unittest.TestCase):

    def test_aggregates_inbound_and_outbound(self):
        raw = [
            {"type": "inbound-rtp", "kind": "audio", "packetsReceived": 100,
             "packetsLost": 1, "bytesReceived": 10_000, "jitter": 0.01},
            {"type": "outbound-rtp", "kind": "audio", "packetsSent": 100,
             "bytesSent": 12_000},
            {"type": "candidate-pair", "kind": "audio"},  # ignored
        ]
        stats = aggregate_stats(raw)
        kinds = {(s.direction, s.kind) for s in stats}
        self.assertEqual(kinds, {("inbound", "audio"), ("outbound", "audio")})

    def test_ignores_non_dict(self):
        stats = aggregate_stats(["not dict", None])  # type: ignore[list-item]
        self.assertEqual(stats, [])

    def test_rejects_non_list(self):
        with self.assertRaises(WebRtcAssertError):
            aggregate_stats({"type": "inbound-rtp"})  # type: ignore[arg-type]  # NOSONAR S5655 — intentional bad-input test


class TestPacketLoss(unittest.TestCase):

    def test_pass_under_threshold(self):
        stats = [RtpStats(direction="inbound", kind="audio", packets=100, packets_lost=1)]
        assert_no_packet_loss(stats, max_loss_ratio=0.05)

    def test_fail_over_threshold(self):
        stats = [RtpStats(direction="inbound", kind="audio", packets=100, packets_lost=10)]
        with self.assertRaises(WebRtcAssertError):
            assert_no_packet_loss(stats, max_loss_ratio=0.05)

    def test_filter_by_direction(self):
        stats = [
            RtpStats(direction="inbound", kind="audio", packets=100, packets_lost=10),
            RtpStats(direction="outbound", kind="audio", packets=100, packets_lost=0),
        ]
        # Only outbound being checked → passes
        assert_no_packet_loss(stats, direction="outbound", max_loss_ratio=0.01)

    def test_bad_ratio(self):
        with self.assertRaises(WebRtcAssertError):
            assert_no_packet_loss([], max_loss_ratio=2.0)


class TestMinBytes(unittest.TestCase):

    def test_pass(self):
        stats = [RtpStats(direction="outbound", kind="video", bytes=10_000)]
        assert_min_bytes_flowed(stats, direction="outbound", kind="video", minimum=1000)

    def test_fail_too_few(self):
        stats = [RtpStats(direction="outbound", kind="video", bytes=10)]
        with self.assertRaises(WebRtcAssertError):
            assert_min_bytes_flowed(stats, direction="outbound", kind="video", minimum=1000)

    def test_missing_stream(self):
        with self.assertRaises(WebRtcAssertError):
            assert_min_bytes_flowed([], direction="outbound", kind="video", minimum=1)

    def test_negative_minimum(self):
        with self.assertRaises(WebRtcAssertError):
            assert_min_bytes_flowed([], direction="x", kind="y", minimum=-1)


class TestExport(unittest.TestCase):

    def test_export(self):
        data = export_snapshot(_connected_snapshot())
        self.assertEqual(data["connection_state"], "connected")
        self.assertEqual(data["ice_connection_state"], "connected")
        self.assertIn("remote_tracks", data)


if __name__ == "__main__":
    unittest.main()
