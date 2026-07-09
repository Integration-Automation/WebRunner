"""
週報 / 日報:quarantine 進出、top-risk PR、flake 趨勢、cost 變化,推到 Slack / Teams。
A digest is just a single Slack Block-Kit payload (or a small Teams card)
that the existing :mod:`notifier` module can post. This module's job is
to *render* the digest from upstream module outputs — pure formatting,
no HTTP.

Tested by snapshot-style assertions on the produced block list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from je_web_runner.utils.exception.exceptions import WebRunnerException


class SlackDigestError(WebRunnerException):
    """Raised on bad input shapes."""


# ---------- inputs ------------------------------------------------------

@dataclass
class FlakeStat:
    """One quarantine list change in the digest window."""

    test_id: str
    action: str  # 'added' | 'released' | 'still_in'
    flake_score: float = 0.0


@dataclass
class RiskyPr:
    """A high-risk PR from :mod:`pr_risk_score` (or any upstream)."""

    number: int
    title: str
    score: float
    url: str = ""


@dataclass
class CostTrend:
    """Period-over-period cost (USD)."""

    current_usd: float
    previous_usd: float

    def delta_pct(self) -> float:
        if self.previous_usd <= 0:
            return 0.0 if self.current_usd <= 0 else 100.0
        return ((self.current_usd - self.previous_usd) / self.previous_usd) * 100.0


@dataclass
class DigestInputs:
    """Everything a digest can include. Each field is optional."""

    period_label: str = "last 7 days"
    flake_changes: list[FlakeStat] = field(default_factory=list)
    risky_prs: list[RiskyPr] = field(default_factory=list)
    cost: CostTrend | None = None
    suite_pass_rate: float | None = None  # 0..1
    suite_pass_rate_previous: float | None = None
    extra_lines: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.suite_pass_rate is not None and not 0.0 <= self.suite_pass_rate <= 1.0:
            raise SlackDigestError("suite_pass_rate must be in [0, 1]")
        if (self.suite_pass_rate_previous is not None
                and not 0.0 <= self.suite_pass_rate_previous <= 1.0):
            raise SlackDigestError("suite_pass_rate_previous must be in [0, 1]")


# ---------- rendering --------------------------------------------------

def _header_block(period_label: str) -> dict[str, Any]:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return {
        "type": "header",
        "text": {"type": "plain_text",
                 "text": f"Test digest — {period_label} (as of {today})"},
    }


def _suite_health_block(inputs: DigestInputs) -> dict[str, Any] | None:
    if inputs.suite_pass_rate is None:
        return None
    pct = inputs.suite_pass_rate * 100
    line = f"*Suite pass rate:* {pct:.1f}%"
    if inputs.suite_pass_rate_previous is not None:
        delta = (inputs.suite_pass_rate - inputs.suite_pass_rate_previous) * 100
        sign = "▲" if delta >= 0 else "▼"
        line += f" ({sign}{abs(delta):.1f} pts vs prev)"
    return {"type": "section", "text": {"type": "mrkdwn", "text": line}}


def _flake_block(stats: Sequence[FlakeStat]) -> dict[str, Any] | None:
    if not stats:
        return None
    added = [s for s in stats if s.action == "added"]
    released = [s for s in stats if s.action == "released"]
    still_in = [s for s in stats if s.action == "still_in"]
    parts: list[str] = ["*Quarantine activity:*"]
    parts.append(f"• Added: {len(added)}")
    parts.append(f"• Released: {len(released)}")
    parts.append(f"• Still in quarantine: {len(still_in)}")
    for stat in added[:5]:
        parts.append(f"  • `{stat.test_id}` (score {stat.flake_score:.2f})")
    if len(added) > 5:
        parts.append(f"  • +{len(added) - 5} more added")
    return {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(parts)}}


def _risky_pr_block(prs: Sequence[RiskyPr]) -> dict[str, Any] | None:
    if not prs:
        return None
    lines = ["*High-risk PRs:*"]
    for pr in sorted(prs, key=lambda p: -p.score)[:5]:
        url = pr.url or f"#{pr.number}"
        lines.append(f"• <{url}|#{pr.number}> {pr.title} — risk {pr.score:.1f}")
    return {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}


def _cost_block(cost: CostTrend | None) -> dict[str, Any] | None:
    if cost is None:
        return None
    delta = cost.delta_pct()
    sign = "▲" if delta >= 0 else "▼"
    line = (
        f"*Estimated test cost:* ${cost.current_usd:,.2f} "
        f"({sign}{abs(delta):.1f}% vs prev ${cost.previous_usd:,.2f})"
    )
    return {"type": "section", "text": {"type": "mrkdwn", "text": line}}


def _extra_block(lines: Sequence[str]) -> dict[str, Any] | None:
    if not lines:
        return None
    text = "\n".join(f"• {line}" for line in lines)
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def build_slack_blocks(inputs: DigestInputs) -> list[dict[str, Any]]:
    """Render the digest as a Slack Block-Kit ``blocks`` list."""
    if not isinstance(inputs, DigestInputs):
        raise SlackDigestError("build_slack_blocks expects DigestInputs")
    candidates = [
        _header_block(inputs.period_label),
        _suite_health_block(inputs),
        _flake_block(inputs.flake_changes),
        _risky_pr_block(inputs.risky_prs),
        _cost_block(inputs.cost),
        _extra_block(inputs.extra_lines),
    ]
    blocks = [b for b in candidates if b]
    if len(blocks) == 1:  # only header → nothing to report
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": "_Nothing notable to report in this period._"},
        })
    return blocks


def build_slack_payload(
    inputs: DigestInputs,
    *,
    channel: str | None = None,
) -> dict[str, Any]:
    """Wrap the blocks in a complete ``chat.postMessage`` payload."""
    payload: dict[str, Any] = {"blocks": build_slack_blocks(inputs)}
    if channel:
        if not isinstance(channel, str):
            raise SlackDigestError("channel must be a string")
        payload["channel"] = channel
    return payload


# ---------- teams card -------------------------------------------------

def build_teams_card(inputs: DigestInputs) -> dict[str, Any]:
    """Render a simple Adaptive Card body for Microsoft Teams webhooks."""
    blocks = build_slack_blocks(inputs)
    body: list[dict[str, Any]] = []
    for block in blocks:
        text = ""
        block_text = block.get("text") or {}
        if isinstance(block_text, dict):
            text = str(block_text.get("text") or "")
        if not text:
            continue
        body.append({
            "type": "TextBlock",
            "text": text,
            "wrap": True,
            "weight": "Bolder" if block.get("type") == "header" else "Default",
        })
    return {
        "type": "AdaptiveCard",
        # S5332 ok: this is the well-known AdaptiveCards $schema literal that
        # Microsoft Teams expects verbatim; it is NOT fetched.
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",  # NOSONAR S5332 — intentional plain HTTP (localhost/dev-configured endpoint), not a security-sensitive transport
        "version": "1.5",
        "body": body,
    }


# ---------- helpers ----------------------------------------------------

def render_plain_text(inputs: DigestInputs) -> str:
    """Render a fallback plain-text digest (email / Markdown alike)."""
    blocks = build_slack_blocks(inputs)
    lines: list[str] = []
    for block in blocks:
        block_text = block.get("text") or {}
        if isinstance(block_text, dict):
            text = str(block_text.get("text") or "")
            if text:
                lines.append(text)
    return "\n\n".join(lines) + "\n"
