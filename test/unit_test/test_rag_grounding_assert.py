"""Unit tests for je_web_runner.utils.rag_grounding_assert."""
import unittest

from je_web_runner.utils.rag_grounding_assert.grounding import (
    Chunk,
    RagAnswer,
    RagGroundingError,
    assert_citations_in_retrieved,
    assert_grounded,
    assert_min_citations,
    assert_no_hallucination,
    find_unsupported_claims,
    lexical_overlap_score,
)


class TestModels(unittest.TestCase):

    def test_chunk_id_required(self):
        with self.assertRaises(RagGroundingError):
            Chunk(chunk_id="", text="x")

    def test_text_must_be_str(self):
        with self.assertRaises(RagGroundingError):
            RagAnswer(text=123)


class TestCitations(unittest.TestCase):

    def test_pass(self):
        assert_citations_in_retrieved(
            RagAnswer(text="x", cited_chunk_ids=["a"]),
            retrieved=[Chunk("a", "x")],
        )

    def test_fail(self):
        with self.assertRaises(RagGroundingError):
            assert_citations_in_retrieved(
                RagAnswer(text="x", cited_chunk_ids=["b"]),
                retrieved=[Chunk("a", "x")],
            )

    def test_min_citations_pass(self):
        assert_min_citations(
            RagAnswer(text="x", cited_chunk_ids=["a"]), minimum=1,
        )

    def test_min_citations_fail(self):
        with self.assertRaises(RagGroundingError):
            assert_min_citations(
                RagAnswer(text="x", cited_chunk_ids=[]), minimum=1,
            )

    def test_bad_min(self):
        with self.assertRaises(RagGroundingError):
            assert_min_citations(RagAnswer(text="x"), minimum=0)


class TestOverlap(unittest.TestCase):

    def test_full_overlap(self):
        score = lexical_overlap_score(
            RagAnswer(text="quick brown fox"),
            [Chunk("a", "the quick brown fox jumps")],
        )
        self.assertEqual(score, 1.0)

    def test_partial(self):
        score = lexical_overlap_score(
            RagAnswer(text="quick brown banana"),
            [Chunk("a", "quick brown fox")],
        )
        self.assertAlmostEqual(score, 2 / 3, places=2)

    def test_empty(self):
        self.assertEqual(
            lexical_overlap_score(RagAnswer(text=""), [Chunk("a", "x")]), 0,
        )

    def test_grounded_pass(self):
        assert_grounded(
            RagAnswer(text="quick brown fox"),
            [Chunk("a", "quick brown fox")],
            min_overlap=0.8,
        )

    def test_grounded_fail(self):
        with self.assertRaises(RagGroundingError):
            assert_grounded(
                RagAnswer(text="totally unrelated"),
                [Chunk("a", "different document")],
                min_overlap=0.8,
            )

    def test_bad_min(self):
        with self.assertRaises(RagGroundingError):
            assert_grounded(RagAnswer(text="x"), [], min_overlap=2)


class TestHallucination(unittest.TestCase):

    def test_supported(self):
        unsupported = find_unsupported_claims(
            RagAnswer(text="the cat sat on the mat"),
            [Chunk("a", "the cat sat on the mat in the morning")],
            min_phrase_len=3,
        )
        self.assertEqual(unsupported, [])

    def test_unsupported(self):
        unsupported = find_unsupported_claims(
            RagAnswer(text="dragons can fly to the moon"),
            [Chunk("a", "dogs can chase squirrels")],
            min_phrase_len=3,
        )
        self.assertGreater(len(unsupported), 0)

    def test_short_answer(self):
        self.assertEqual(
            find_unsupported_claims(RagAnswer(text="hi"), [], min_phrase_len=4),
            [],
        )

    def test_bad_phrase_len(self):
        with self.assertRaises(RagGroundingError):
            find_unsupported_claims(RagAnswer(text="x"), [], min_phrase_len=1)

    def test_no_hallucination_pass(self):
        assert_no_hallucination(
            RagAnswer(text="the cat sat on the mat"),
            [Chunk("a", "the cat sat on the mat in the morning")],
            min_phrase_len=3,
        )

    def test_no_hallucination_fail(self):
        with self.assertRaises(RagGroundingError):
            assert_no_hallucination(
                RagAnswer(text="dragons can fly to the moon and back"),
                [Chunk("a", "dogs can chase squirrels")],
                min_phrase_len=3,
            )


if __name__ == "__main__":
    unittest.main()
