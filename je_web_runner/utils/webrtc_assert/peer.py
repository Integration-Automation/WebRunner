"""
PeerConnection 狀態 / ICE / track / RTP stats 斷言。
WebRTC apps are notoriously hard to test: the peer connection lifecycle
crosses ``new → connecting → connected → completed → disconnected →
failed → closed``, and the actual media flow shows up only in
``getStats()`` (RTP packets sent/received, jitter, packets lost).

This module ingests JSON snapshots of either:

* ``RTCPeerConnection`` instance state (``connectionState``,
  ``iceConnectionState``, ``signalingState``, ``localDescription`` SDP,
  remote tracks)
* the ``getStats()`` ``RTCStatsReport`` dict (an array of stats records
  with ``type``: ``inbound-rtp`` / ``outbound-rtp`` / ``candidate-pair``)

…and exposes a fluent set of asserts that work regardless of how you
captured the data (CDP, BiDi, Playwright eval).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class WebRtcAssertError(WebRunnerException):
    """Raised on malformed peer/state input or failed assertion."""


# ---------- enums -------------------------------------------------------

class ConnectionState(str, Enum):
    NEW = "new"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    CLOSED = "closed"


class IceState(str, Enum):
    NEW = "new"
    CHECKING = "checking"
    CONNECTED = "connected"
    COMPLETED = "completed"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    CLOSED = "closed"


class SignalingState(str, Enum):
    STABLE = "stable"
    HAVE_LOCAL_OFFER = "have-local-offer"
    HAVE_REMOTE_OFFER = "have-remote-offer"
    HAVE_LOCAL_PRANSWER = "have-local-pranswer"
    HAVE_REMOTE_PRANSWER = "have-remote-pranswer"
    CLOSED = "closed"


# ---------- snapshot model ---------------------------------------------

@dataclass
class TrackInfo:
    """One remote / local track summary."""

    kind: str  # 'audio' | 'video'
    enabled: bool = True
    muted: bool = False
    ready_state: str = "live"  # 'live' | 'ended'
    label: str = ""


@dataclass
class PeerSnapshot:
    """A point-in-time view of an ``RTCPeerConnection``."""

    connection_state: ConnectionState
    ice_connection_state: IceState
    signaling_state: SignalingState = SignalingState.STABLE
    local_sdp: str = ""
    remote_sdp: str = ""
    local_tracks: List[TrackInfo] = field(default_factory=list)
    remote_tracks: List[TrackInfo] = field(default_factory=list)
    selected_candidate_pair_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PeerSnapshot":
        """Build from a raw JSON dict (e.g. ``page.evaluate(...)`` result)."""
        if not isinstance(data, dict):
            raise WebRtcAssertError(f"from_dict expects dict, got {type(data).__name__}")
        try:
            cs = ConnectionState(data.get("connectionState") or "new")
            ice = IceState(data.get("iceConnectionState") or "new")
            sig = SignalingState(data.get("signalingState") or "stable")
        except ValueError as error:
            raise WebRtcAssertError(f"unknown state value: {error}") from error
        return cls(
            connection_state=cs,
            ice_connection_state=ice,
            signaling_state=sig,
            local_sdp=str(data.get("localSdp") or ""),
            remote_sdp=str(data.get("remoteSdp") or ""),
            local_tracks=_coerce_tracks(data.get("localTracks") or []),
            remote_tracks=_coerce_tracks(data.get("remoteTracks") or []),
            selected_candidate_pair_id=data.get("selectedCandidatePairId"),
        )


def _coerce_tracks(items: Iterable[Any]) -> List[TrackInfo]:
    out: List[TrackInfo] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(TrackInfo(
            kind=str(item.get("kind") or ""),
            enabled=bool(item.get("enabled", True)),
            muted=bool(item.get("muted", False)),
            ready_state=str(item.get("readyState") or "live"),
            label=str(item.get("label") or ""),
        ))
    return out


# ---------- stats model -------------------------------------------------

@dataclass
class RtpStats:
    """Summary derived from ``getStats()`` for one direction + kind."""

    direction: str  # 'inbound' | 'outbound'
    kind: str       # 'audio' | 'video'
    packets: int = 0
    packets_lost: int = 0
    bytes: int = 0
    jitter: float = 0.0


def aggregate_stats(stats_report: Sequence[Dict[str, Any]]) -> List[RtpStats]:
    """Reduce a raw ``getStats()`` list into one :class:`RtpStats` per direction+kind."""
    if not isinstance(stats_report, list):
        raise WebRtcAssertError(
            f"stats_report must be a list, got {type(stats_report).__name__}"
        )
    bucket: Dict[tuple, RtpStats] = {}
    for record in stats_report:
        if not isinstance(record, dict):
            continue
        rec_type = record.get("type")
        if rec_type not in ("inbound-rtp", "outbound-rtp"):
            continue
        kind = str(record.get("kind") or "")
        if not kind:
            continue
        direction = "inbound" if rec_type == "inbound-rtp" else "outbound"
        key = (direction, kind)
        agg = bucket.setdefault(key, RtpStats(direction=direction, kind=kind))
        agg.packets += int(record.get("packetsReceived" if direction == "inbound" else "packetsSent") or 0)
        agg.packets_lost += int(record.get("packetsLost") or 0)
        agg.bytes += int(record.get("bytesReceived" if direction == "inbound" else "bytesSent") or 0)
        jitter_val = record.get("jitter")
        if isinstance(jitter_val, (int, float)):
            agg.jitter = max(agg.jitter, float(jitter_val))
    return list(bucket.values())


# ---------- assertions --------------------------------------------------

def assert_connected(snapshot: PeerSnapshot) -> None:
    """Assert the peer is in the ``connected`` (or ``completed``) state."""
    if not isinstance(snapshot, PeerSnapshot):
        raise WebRtcAssertError("assert_connected expects PeerSnapshot")
    if snapshot.connection_state != ConnectionState.CONNECTED:
        raise WebRtcAssertError(
            f"connectionState is {snapshot.connection_state.value!r}, want 'connected'"
        )
    if snapshot.ice_connection_state not in (IceState.CONNECTED, IceState.COMPLETED):
        raise WebRtcAssertError(
            f"iceConnectionState is {snapshot.ice_connection_state.value!r}, "
            "want 'connected' or 'completed'"
        )


def assert_track_present(
    snapshot: PeerSnapshot,
    kind: str,
    *,
    side: str = "remote",
    require_live: bool = True,
) -> TrackInfo:
    """Assert a track of ``kind`` exists on the chosen side."""
    if side not in ("remote", "local"):
        raise WebRtcAssertError(f"side must be 'remote' or 'local', got {side!r}")
    tracks = snapshot.remote_tracks if side == "remote" else snapshot.local_tracks
    for track in tracks:
        if track.kind == kind:
            if require_live and track.ready_state != "live":
                continue
            return track
    raise WebRtcAssertError(
        f"no live {side} {kind!r} track in snapshot ({len(tracks)} total)"
    )


def assert_sdp_has_codec(snapshot: PeerSnapshot, codec_name: str, *, side: str = "local") -> None:
    """Assert the SDP for the chosen side advertises ``codec_name`` (e.g. 'opus')."""
    if not isinstance(codec_name, str) or not codec_name:
        raise WebRtcAssertError("codec_name must be a non-empty string")
    sdp = snapshot.local_sdp if side == "local" else snapshot.remote_sdp
    if not sdp:
        raise WebRtcAssertError(f"{side} SDP is empty")
    if codec_name.lower() not in sdp.lower():
        raise WebRtcAssertError(
            f"{side} SDP does not advertise codec {codec_name!r}"
        )


def assert_no_packet_loss(
    stats: Sequence[RtpStats],
    *,
    direction: Optional[str] = None,
    max_loss_ratio: float = 0.01,
) -> None:
    """Assert packets_lost / packets <= ``max_loss_ratio`` for matching streams."""
    if not 0.0 <= max_loss_ratio <= 1.0:
        raise WebRtcAssertError("max_loss_ratio must be in [0, 1]")
    breaches: List[str] = []
    for s in stats:
        if direction is not None and s.direction != direction:
            continue
        if s.packets <= 0:
            continue
        ratio = s.packets_lost / s.packets
        if ratio > max_loss_ratio:
            breaches.append(
                f"{s.direction}/{s.kind}: {s.packets_lost}/{s.packets} ({ratio:.2%})"
            )
    if breaches:
        raise WebRtcAssertError(
            f"packet loss above {max_loss_ratio:.2%}: " + "; ".join(breaches)
        )


def assert_min_bytes_flowed(
    stats: Sequence[RtpStats],
    *,
    direction: str,
    kind: str,
    minimum: int,
) -> None:
    """Assert that at least ``minimum`` bytes flowed for the given stream."""
    if minimum < 0:
        raise WebRtcAssertError("minimum must be >= 0")
    for s in stats:
        if s.direction == direction and s.kind == kind:
            if s.bytes < minimum:
                raise WebRtcAssertError(
                    f"{direction}/{kind} only saw {s.bytes} bytes, want >= {minimum}"
                )
            return
    raise WebRtcAssertError(
        f"no {direction}/{kind} stats found to check byte threshold"
    )


# ---------- helpers -----------------------------------------------------

def export_snapshot(snapshot: PeerSnapshot) -> Dict[str, Any]:
    """Render the snapshot as a plain dict (for failure bundles)."""
    out = asdict(snapshot)
    out["connection_state"] = snapshot.connection_state.value
    out["ice_connection_state"] = snapshot.ice_connection_state.value
    out["signaling_state"] = snapshot.signaling_state.value
    return out
