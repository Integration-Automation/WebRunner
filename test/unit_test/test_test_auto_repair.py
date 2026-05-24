"""Unit tests for je_web_runner.utils.test_auto_repair."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from je_web_runner.utils.ai_assist.llm_assist import set_llm_callable
from je_web_runner.utils.failure_bundle.bundle import FailureBundle
from je_web_runner.utils.failure_triage.triage import TriageSignals
from je_web_runner.utils.test_auto_repair.repair import (
    RepairPlan,
    TestAutoRepairError,
    apply_repair,
    collect_git_diff,
    propose_repair,
    render_repair_markdown,
    repair_from_bundle,
)


_VALID_PAYLOAD = {
    "summary": "Locator drifted; replaced #old-btn with [data-testid='submit']",
    "confidence": 0.8,
    "repaired_actions": [
        ["WR_save_test_object", {"object_type": "CSS_SELECTOR",
                                  "test_object_name": "[data-testid='submit']"}],
        ["WR_element_click", {"test_object_name": "[data-testid='submit']"}],
    ],
    "changes": [
        {"index": 0, "kind": "locator",
         "before": "#old-btn", "after": "[data-testid='submit']",
         "why": "DOM no longer has #old-btn"},
    ],
    "risks": ["double-check submit handler still wires on test-id"],
}


class TestCollectGitDiff(unittest.TestCase):

    def test_returns_stdout_on_success(self):
        fake = MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="--- diff text ---", stderr="",
        ))
        text = collect_git_diff("/some/repo", runner=fake)
        self.assertIn("diff text", text)

    def test_returns_empty_on_failure(self):
        fake = MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=128, stdout="", stderr="not a git repo",
        ))
        self.assertEqual(collect_git_diff("/x", runner=fake), "")

    def test_returns_empty_on_oserror(self):
        def boom(*_a, **_kw):
            raise OSError("git missing")
        self.assertEqual(collect_git_diff("/x", runner=boom), "")

    def test_truncates_long_diffs(self):
        fake = MagicMock(return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="x" * 9999, stderr="",
        ))
        text = collect_git_diff("/x", runner=fake, max_chars=100)
        self.assertLessEqual(len(text), 200)  # 100 + truncated marker
        self.assertIn("truncated", text)


class TestProposeRepair(unittest.TestCase):

    def setUp(self):
        self.signals = TriageSignals(
            test_name="login_test",
            error_repr="TimeoutException: #old-btn not found",
            error_signature="timeoutexception: #old-btn not found",
            last_steps=[["WR_element_click", {"test_object_name": "#old-btn"}]],
        )
        self.actions = [
            ["WR_save_test_object", {"object_type": "CSS_SELECTOR",
                                      "test_object_name": "#old-btn"}],
            ["WR_element_click", {"test_object_name": "#old-btn"}],
        ]

    def tearDown(self):
        set_llm_callable(None)

    def test_valid_payload_returns_plan(self):
        set_llm_callable(lambda _p: json.dumps(_VALID_PAYLOAD))
        plan = propose_repair(self.actions, self.signals)
        self.assertEqual(len(plan.repaired_actions), 2)
        self.assertAlmostEqual(plan.confidence, 0.8)
        self.assertEqual(plan.changes[0]["kind"], "locator")

    def test_missing_callable_raises(self):
        set_llm_callable(None)
        with self.assertRaises(TestAutoRepairError):
            propose_repair(self.actions, self.signals)

    def test_non_list_actions_raise(self):
        with self.assertRaises(TestAutoRepairError):
            propose_repair("not a list", self.signals)  # type: ignore[arg-type]

    def test_missing_repaired_actions_raises(self):
        payload = dict(_VALID_PAYLOAD)
        del payload["repaired_actions"]
        set_llm_callable(lambda _p: json.dumps(payload))
        with self.assertRaises(TestAutoRepairError):
            propose_repair(self.actions, self.signals)

    def test_repaired_actions_not_list_raises(self):
        payload = dict(_VALID_PAYLOAD)
        payload["repaired_actions"] = "oops"
        set_llm_callable(lambda _p: json.dumps(payload))
        with self.assertRaises(TestAutoRepairError):
            propose_repair(self.actions, self.signals)

    def test_invalid_json_raises(self):
        set_llm_callable(lambda _p: "not json")
        with self.assertRaises(TestAutoRepairError):
            propose_repair(self.actions, self.signals)

    def test_confidence_clamped(self):
        payload = dict(_VALID_PAYLOAD)
        payload["confidence"] = 5.0
        set_llm_callable(lambda _p: json.dumps(payload))
        plan = propose_repair(self.actions, self.signals)
        self.assertEqual(plan.confidence, 1.0)

    def test_string_risks_coerced(self):
        payload = dict(_VALID_PAYLOAD)
        payload["risks"] = "single risk note"
        set_llm_callable(lambda _p: json.dumps(payload))
        plan = propose_repair(self.actions, self.signals)
        self.assertEqual(plan.risks, ["single risk note"])


class TestRepairFromBundle(unittest.TestCase):

    def tearDown(self):
        set_llm_callable(None)

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            action_path = Path(tmpdir) / "a.json"
            action_path.write_text(json.dumps([
                ["WR_element_click", {"test_object_name": "#old-btn"}],
            ]), encoding="utf-8")
            bundle = FailureBundle(test_name="t", error_repr="boom")
            bundle_path = bundle.write(Path(tmpdir) / "b.zip")
            set_llm_callable(lambda _p: json.dumps(_VALID_PAYLOAD))
            fake_git = MagicMock(return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="diff --git", stderr="",
            ))
            plan = repair_from_bundle(
                action_path, bundle_path,
                repo_dir=tmpdir, git_runner=fake_git,
            )
            self.assertGreater(len(plan.repaired_actions), 0)

    def test_missing_action_file_raises(self):
        with self.assertRaises(TestAutoRepairError):
            repair_from_bundle("/no/such.json", "/no/such.zip")


class TestApplyRepair(unittest.TestCase):

    def test_writes_side_file_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "a.json"
            src.write_text(json.dumps([["WR_x"]]), encoding="utf-8")
            plan = RepairPlan(
                summary="ok", confidence=0.9,
                repaired_actions=[["WR_y"]],
            )
            target = apply_repair(src, plan)
            self.assertEqual(target.name, "a.json.repaired.json")
            self.assertNotEqual(target, src)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload, [["WR_y"]])

    def test_low_confidence_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "a.json"
            src.write_text("[]", encoding="utf-8")
            plan = RepairPlan(summary="x", confidence=0.2, repaired_actions=[])
            with self.assertRaises(TestAutoRepairError):
                apply_repair(src, plan)

    def test_explicit_output_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "a.json"
            src.write_text("[]", encoding="utf-8")
            out = Path(tmpdir) / "subdir" / "b.json"
            plan = RepairPlan(summary="x", confidence=0.9, repaired_actions=[1])
            applied = apply_repair(src, plan, output_path=out)
            self.assertEqual(applied, out)
            self.assertTrue(out.exists())


class TestRenderMarkdown(unittest.TestCase):

    def test_includes_changes_and_risks(self):
        plan = RepairPlan(
            summary="rewired locator", confidence=0.8,
            repaired_actions=[],
            changes=[{"index": 0, "kind": "locator", "why": "drift"}],
            risks=["double check"],
        )
        md = render_repair_markdown(plan)
        self.assertIn("AI Test Auto-Repair", md)
        self.assertIn("80%", md)
        self.assertIn("`locator`", md)
        self.assertIn("double check", md)


if __name__ == "__main__":
    unittest.main()
