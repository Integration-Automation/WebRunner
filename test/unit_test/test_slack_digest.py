"""Unit tests for je_web_runner.utils.slack_digest."""
import json
import unittest

from je_web_runner.utils.slack_digest.digest import (
    CostTrend,
    DigestInputs,
    FlakeStat,
    RiskyPr,
    SlackDigestError,
    build_slack_blocks,
    build_slack_payload,
    build_teams_card,
    render_plain_text,
)


def _full_inputs():
    return DigestInputs(
        period_label="last 7 days",
        flake_changes=[
            FlakeStat(test_id="t1.json", action="added", flake_score=0.55),
            FlakeStat(test_id="t2.json", action="released", flake_score=0.05),
            FlakeStat(test_id="t3.json", action="still_in", flake_score=0.4),
        ],
        risky_prs=[
            RiskyPr(number=42, title="Auth rewrite", score=78.0,
                    url="https://github.com/x/y/pull/42"),
            RiskyPr(number=43, title="Tiny tweak", score=20.0),
        ],
        cost=CostTrend(current_usd=120.0, previous_usd=100.0),
        suite_pass_rate=0.94,
        suite_pass_rate_previous=0.91,
        extra_lines=["3 quarantined tests released back to main"],
    )


class TestInputsValidation(unittest.TestCase):

    def test_bad_pass_rate(self):
        with self.assertRaises(SlackDigestError):
            DigestInputs(suite_pass_rate=1.5)

    def test_bad_previous_pass_rate(self):
        with self.assertRaises(SlackDigestError):
            DigestInputs(suite_pass_rate_previous=-1)


class TestCostTrend(unittest.TestCase):

    def test_delta(self):
        self.assertEqual(CostTrend(current_usd=110, previous_usd=100).delta_pct(), 10.0)

    def test_delta_zero_previous(self):
        self.assertEqual(CostTrend(current_usd=100, previous_usd=0).delta_pct(), 100.0)
        self.assertEqual(CostTrend(current_usd=0, previous_usd=0).delta_pct(), 0.0)


class TestSlackBlocks(unittest.TestCase):

    def test_renders_all_sections(self):
        blocks = build_slack_blocks(_full_inputs())
        block_types = [b["type"] for b in blocks]
        # header + 5 sections
        self.assertEqual(block_types[0], "header")
        self.assertGreaterEqual(block_types.count("section"), 4)

    def test_minimum_input_renders_nothing_notable(self):
        blocks = build_slack_blocks(DigestInputs())
        joined = json.dumps(blocks)
        self.assertIn("Nothing notable", joined)

    def test_flake_block_omitted_when_empty(self):
        blocks = build_slack_blocks(DigestInputs(suite_pass_rate=0.9))
        joined = json.dumps(blocks)
        self.assertNotIn("Quarantine activity", joined)

    def test_high_risk_pr_uses_url(self):
        blocks = build_slack_blocks(DigestInputs(
            risky_prs=[RiskyPr(number=99, title="Big change", score=80.0,
                               url="https://gh/x/y/pull/99")],
        ))
        joined = json.dumps(blocks)
        self.assertIn("https://gh/x/y/pull/99", joined)
        self.assertIn("Big change", joined)

    def test_pass_rate_block_includes_delta(self):
        blocks = build_slack_blocks(DigestInputs(
            suite_pass_rate=0.95, suite_pass_rate_previous=0.90,
        ))
        joined = json.dumps(blocks)
        self.assertIn("95.0%", joined)
        self.assertIn("pts vs prev", joined)

    def test_rejects_non_inputs(self):
        with self.assertRaises(SlackDigestError):
            build_slack_blocks("nope")  # type: ignore[arg-type]

    def test_extra_lines_rendered(self):
        blocks = build_slack_blocks(DigestInputs(
            extra_lines=["something interesting"],
        ))
        joined = json.dumps(blocks)
        self.assertIn("something interesting", joined)


class TestPayload(unittest.TestCase):

    def test_without_channel(self):
        payload = build_slack_payload(_full_inputs())
        self.assertNotIn("channel", payload)
        self.assertIn("blocks", payload)

    def test_with_channel(self):
        payload = build_slack_payload(_full_inputs(), channel="#qa")
        self.assertEqual(payload["channel"], "#qa")

    def test_bad_channel(self):
        with self.assertRaises(SlackDigestError):
            build_slack_payload(_full_inputs(), channel=123)  # type: ignore[arg-type]


class TestTeamsCard(unittest.TestCase):

    def test_basic_shape(self):
        card = build_teams_card(_full_inputs())
        self.assertEqual(card["type"], "AdaptiveCard")
        self.assertGreater(len(card["body"]), 1)
        # Header rendered bolder
        self.assertEqual(card["body"][0]["weight"], "Bolder")


class TestPlainText(unittest.TestCase):

    def test_renders_text(self):
        text = render_plain_text(_full_inputs())
        self.assertIn("Test digest", text)
        self.assertIn("Quarantine activity", text)

    def test_minimum_input(self):
        text = render_plain_text(DigestInputs())
        self.assertIn("Nothing notable", text)


if __name__ == "__main__":
    unittest.main()
