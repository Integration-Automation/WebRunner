"""Unit tests for je_web_runner.utils.mutation_testing."""
import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.mutation_testing.mutator import (
    Mutation,
    MutationScore,
    MutationTestingError,
    MutationType,
    apply_mutation,
    assert_min_score,
    generate_mutations,
    render_mutation_markdown,
    run_mutation_testing,
    run_mutation_testing_on_file,
)


SAMPLE_ACTIONS = [
    ["WR_to_url", {"url": "https://shop/login"}],
    ["WR_save_test_object", {"test_object_name": "user", "object_type": "ID"}],
    ["WR_element_input", {"test_object_name": "user", "text": "alice", "timeout": 10}],
    ["WR_element_click", {"test_object_name": "submit"}],
    ["WR_element_assert", {"test_object_name": "welcome", "expected_text": "Hi alice"}],
]


class TestGenerateMutations(unittest.TestCase):

    def test_all_types_produce_at_least_one(self):
        mutations = generate_mutations(SAMPLE_ACTIONS)
        types = {m.type for m in mutations}
        self.assertIn(MutationType.LOCATOR_SWAP, types)
        self.assertIn(MutationType.TIMEOUT_SHRINK, types)
        self.assertIn(MutationType.URL_CHANGE, types)
        self.assertIn(MutationType.ASSERTION_FLIP, types)
        self.assertIn(MutationType.ACTION_REMOVAL, types)
        self.assertIn(MutationType.ADJACENT_REORDER, types)

    def test_max_per_type_caps(self):
        mutations = generate_mutations(SAMPLE_ACTIONS, max_per_type=1, seed=42)
        per_type: dict = {}
        for m in mutations:
            per_type[m.type] = per_type.get(m.type, 0) + 1
        for count in per_type.values():
            self.assertLessEqual(count, 1)

    def test_non_list_raises(self):
        with self.assertRaises(MutationTestingError):
            generate_mutations("not a list")  # type: ignore[arg-type]

    def test_url_change_skips_non_url(self):
        actions = [["WR_element_click", {"test_object_name": "x"}]]
        mutations = generate_mutations(actions, types=[MutationType.URL_CHANGE])
        self.assertEqual(mutations, [])

    def test_action_removal_skips_quit_init(self):
        actions = [
            ["WR_init", {}],
            ["WR_element_click", {"test_object_name": "x"}],
            ["WR_quit_all"],
        ]
        mutations = generate_mutations(actions, types=[MutationType.ACTION_REMOVAL])
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0].action_index, 1)


class TestApplyMutation(unittest.TestCase):

    def test_locator_swap(self):
        m = Mutation(
            type=MutationType.LOCATOR_SWAP, action_index=1,
            description="x", original="user", mutated="__mutated__",
        )
        new = apply_mutation(SAMPLE_ACTIONS, m)
        self.assertEqual(new[1][1]["test_object_name"], "__mutated__")
        self.assertEqual(SAMPLE_ACTIONS[1][1]["test_object_name"], "user")

    def test_timeout_shrink(self):
        m = Mutation(
            type=MutationType.TIMEOUT_SHRINK, action_index=2,
            description="x", original=10, mutated=0.001,
        )
        new = apply_mutation(SAMPLE_ACTIONS, m)
        self.assertEqual(new[2][1]["timeout"], 0.001)

    def test_url_change(self):
        m = Mutation(
            type=MutationType.URL_CHANGE, action_index=0,
            description="x", original="https://shop/login",
            mutated="https://example.invalid/mut",
        )
        new = apply_mutation(SAMPLE_ACTIONS, m)
        self.assertEqual(new[0][1]["url"], "https://example.invalid/mut")

    def test_assertion_flip_string(self):
        m = Mutation(
            type=MutationType.ASSERTION_FLIP, action_index=4,
            description="x", original="Hi alice",
            mutated="Hi alice__MUTATED__",
        )
        new = apply_mutation(SAMPLE_ACTIONS, m)
        self.assertEqual(new[4][1]["expected_text"], "Hi alice__MUTATED__")

    def test_action_removal_shortens_list(self):
        m = Mutation(
            type=MutationType.ACTION_REMOVAL, action_index=3,
            description="remove click", original=SAMPLE_ACTIONS[3], mutated=None,
        )
        new = apply_mutation(SAMPLE_ACTIONS, m)
        self.assertEqual(len(new), len(SAMPLE_ACTIONS) - 1)

    def test_adjacent_reorder_swaps(self):
        m = Mutation(
            type=MutationType.ADJACENT_REORDER, action_index=2,
            description="x", original=("WR_element_input", "WR_element_click"),
            mutated=("WR_element_click", "WR_element_input"),
        )
        new = apply_mutation(SAMPLE_ACTIONS, m)
        self.assertEqual(new[2][0], "WR_element_click")
        self.assertEqual(new[3][0], "WR_element_input")

    def test_out_of_range_raises(self):
        m = Mutation(
            type=MutationType.LOCATOR_SWAP, action_index=99,
            description="x", original="user", mutated="x",
        )
        with self.assertRaises(MutationTestingError):
            apply_mutation(SAMPLE_ACTIONS, m)

    def test_reorder_at_last_index_raises(self):
        m = Mutation(
            type=MutationType.ADJACENT_REORDER, action_index=len(SAMPLE_ACTIONS) - 1,
            description="x", original=("a", "b"), mutated=("b", "a"),
        )
        with self.assertRaises(MutationTestingError):
            apply_mutation(SAMPLE_ACTIONS, m)


class TestRunMutationTesting(unittest.TestCase):

    def test_all_killed_when_executor_always_fails(self):
        score = run_mutation_testing(SAMPLE_ACTIONS, lambda _a: False)
        self.assertEqual(score.killed, score.total)
        self.assertEqual(score.survived, 0)
        self.assertEqual(score.score, 1.0)

    def test_all_survived_when_executor_always_passes(self):
        score = run_mutation_testing(SAMPLE_ACTIONS, lambda _a: True)
        self.assertEqual(score.killed, 0)
        self.assertEqual(score.survived, score.total)
        self.assertEqual(score.score, 0.0)

    def test_executor_exception_counts_as_kill(self):
        def boom(_a):
            raise RuntimeError("boom")
        score = run_mutation_testing(
            SAMPLE_ACTIONS, boom,
            types=[MutationType.LOCATOR_SWAP],
        )
        self.assertTrue(all(r.killed for r in score.results))
        self.assertTrue(all(r.error for r in score.results))

    def test_stop_on_first_survivor(self):
        calls = {"n": 0}

        def survivor(_a):
            calls["n"] += 1
            return True  # always pass

        score = run_mutation_testing(
            SAMPLE_ACTIONS, survivor,
            types=[MutationType.LOCATOR_SWAP],
            stop_on_first_survivor=True,
        )
        self.assertEqual(calls["n"], 1)
        self.assertEqual(score.total, 1)
        self.assertEqual(score.survived, 1)


class TestRunOnFile(unittest.TestCase):

    def test_missing_file_raises(self):
        with self.assertRaises(MutationTestingError):
            run_mutation_testing_on_file("/no/such.json", lambda _a: False)

    def test_malformed_top_level_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.json"
            path.write_text('{"not": "a list"}', encoding="utf-8")
            with self.assertRaises(MutationTestingError):
                run_mutation_testing_on_file(path, lambda _a: False)

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "a.json"
            path.write_text(json.dumps(SAMPLE_ACTIONS), encoding="utf-8")
            score = run_mutation_testing_on_file(path, lambda _a: False)
            self.assertGreater(score.total, 0)
            self.assertEqual(score.killed, score.total)


class TestRendering(unittest.TestCase):

    def test_markdown_includes_survivors(self):
        score = run_mutation_testing(SAMPLE_ACTIONS, lambda _a: True)
        md = render_mutation_markdown(score)
        self.assertIn("Mutation score", md)
        self.assertIn("Surviving mutations", md)

    def test_markdown_omits_survivors_when_none(self):
        score = run_mutation_testing(SAMPLE_ACTIONS, lambda _a: False)
        md = render_mutation_markdown(score)
        self.assertNotIn("Surviving mutations", md)


class TestAssertMinScore(unittest.TestCase):

    def test_pass(self):
        score = MutationScore(total=10, killed=9, survived=1, score=0.9)
        assert_min_score(score, minimum=0.8)

    def test_fail(self):
        score = MutationScore(total=10, killed=5, survived=5, score=0.5)
        with self.assertRaises(MutationTestingError):
            assert_min_score(score, minimum=0.8)


if __name__ == "__main__":
    unittest.main()
