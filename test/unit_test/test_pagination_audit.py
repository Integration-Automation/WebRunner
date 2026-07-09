"""Unit tests for je_web_runner.utils.pagination_audit."""
import unittest

from je_web_runner.utils.pagination_audit.audit import (
    Page,
    PaginationAuditError,
    PaginationFindings,
    assert_clean,
    assert_expected_total,
    assert_no_cursor_loop,
    assert_no_duplicates,
    assert_sorted_by,
    assert_terminated,
    walk_all_pages,
)


def _fetcher(pages):
    """pages: list of (items, next_cursor) tuples; first call sees cursor=None."""
    by_cursor = {}
    for index, (items, next_cursor) in enumerate(pages):
        cursor_in = None if index == 0 else pages[index - 1][1]
        by_cursor[cursor_in] = Page(items=list(items), next_cursor=next_cursor)
    def _f(cursor):
        return by_cursor[cursor]
    return _f


class TestPage(unittest.TestCase):

    def test_rejects_non_list_items(self):
        with self.assertRaises(PaginationAuditError):
            Page(items="not list")  # type: ignore[arg-type]


class TestWalk(unittest.TestCase):

    def test_clean_walk(self):
        pages = [
            ([{"id": 1}, {"id": 2}], "c2"),
            ([{"id": 3}, {"id": 4}], None),
        ]
        findings = walk_all_pages(_fetcher(pages), lambda r: r["id"])
        self.assertEqual(findings.page_count, 2)
        self.assertEqual(findings.total_items, 4)
        self.assertEqual(findings.unique_items, 4)
        self.assertTrue(findings.passed())

    def test_duplicate_caught(self):
        pages = [
            ([{"id": 1}, {"id": 2}], "c2"),
            ([{"id": 2}, {"id": 3}], None),
        ]
        findings = walk_all_pages(_fetcher(pages), lambda r: r["id"])
        self.assertIn(2, findings.duplicates)
        self.assertFalse(findings.passed())

    def test_cursor_loop(self):
        # c2 → c1 → c2 → ...
        responses = iter([
            Page(items=[{"id": 1}], next_cursor="c2"),
            Page(items=[{"id": 2}], next_cursor="c1"),
            Page(items=[{"id": 1}], next_cursor="c2"),
        ])
        def fetcher(_cursor):
            return next(responses)
        findings = walk_all_pages(fetcher, lambda r: r["id"])
        self.assertTrue(findings.cursor_loop)

    def test_max_pages_hit(self):
        # always returns a new cursor → would run forever
        def fetcher(cursor):
            n = (cursor or 0) + 1
            return Page(items=[{"id": n}], next_cursor=n)
        findings = walk_all_pages(fetcher, lambda r: r["id"], max_pages=5)
        self.assertTrue(findings.hit_max_pages)
        self.assertEqual(findings.page_count, 5)

    def test_empty_pages_recorded(self):
        pages = [
            ([], "c2"),
            ([{"id": 1}], None),
        ]
        findings = walk_all_pages(_fetcher(pages), lambda r: r["id"])
        self.assertEqual(findings.empty_pages, [0])

    def test_fetcher_must_be_callable(self):
        with self.assertRaises(PaginationAuditError):
            walk_all_pages("not callable", lambda r: r)  # type: ignore[arg-type]

    def test_key_fn_must_be_callable(self):
        with self.assertRaises(PaginationAuditError):
            walk_all_pages(lambda c: Page(items=[]), "not callable")  # type: ignore[arg-type]

    def test_bad_max_pages(self):
        with self.assertRaises(PaginationAuditError):
            walk_all_pages(lambda c: Page(items=[]), lambda r: r, max_pages=0)

    def test_fetcher_must_return_page(self):
        with self.assertRaises(PaginationAuditError):
            walk_all_pages(lambda c: "not a page", lambda r: r)

    def test_fetcher_exception(self):
        def boom(_c):
            raise RuntimeError("net")
        with self.assertRaises(PaginationAuditError):
            walk_all_pages(boom, lambda r: r)

    def test_key_fn_exception(self):
        def runner(c):
            return Page(items=[{"id": 1}])
        def bad(_item):
            raise RuntimeError("nope")
        with self.assertRaises(PaginationAuditError):
            walk_all_pages(runner, bad)


class TestAssertions(unittest.TestCase):

    def test_assert_no_duplicates_pass(self):
        assert_no_duplicates(PaginationFindings())

    def test_assert_no_duplicates_fail(self):
        with self.assertRaises(PaginationAuditError):
            assert_no_duplicates(PaginationFindings(duplicates=[1, 2]))

    def test_assert_no_cursor_loop_pass(self):
        assert_no_cursor_loop(PaginationFindings())

    def test_assert_no_cursor_loop_fail(self):
        with self.assertRaises(PaginationAuditError):
            assert_no_cursor_loop(PaginationFindings(cursor_loop=True))

    def test_assert_terminated(self):
        with self.assertRaises(PaginationAuditError):
            assert_terminated(PaginationFindings(hit_max_pages=True))

    def test_assert_expected_total_pass(self):
        assert_expected_total(
            PaginationFindings(unique_items=5), expected_total=5,
        )

    def test_assert_expected_total_fail(self):
        with self.assertRaises(PaginationAuditError):
            assert_expected_total(
                PaginationFindings(unique_items=4), expected_total=5,
            )

    def test_assert_expected_total_bad_arg(self):
        with self.assertRaises(PaginationAuditError):
            assert_expected_total(PaginationFindings(), expected_total=-1)

    def test_assert_clean_pass(self):
        assert_clean(PaginationFindings())

    def test_assert_clean_rejects_non_findings(self):
        with self.assertRaises(PaginationAuditError):
            assert_clean("nope")  # type: ignore[arg-type]


class TestAssertSortedBy(unittest.TestCase):

    def test_pass_ascending(self):
        findings = PaginationFindings(item_keys_by_page=[[1, 2], [3, 4]])
        assert_sorted_by(findings, lambda x: x)

    def test_fail_ascending(self):
        findings = PaginationFindings(item_keys_by_page=[[3], [1]])
        with self.assertRaises(PaginationAuditError):
            assert_sorted_by(findings, lambda x: x)

    def test_pass_reverse(self):
        findings = PaginationFindings(item_keys_by_page=[[5, 4], [3, 2]])
        assert_sorted_by(findings, lambda x: x, reverse=True)

    def test_empty_passes(self):
        assert_sorted_by(PaginationFindings(), lambda x: x)

    def test_bad_keyfn(self):
        with self.assertRaises(PaginationAuditError):
            assert_sorted_by(PaginationFindings(), "nope")  # type: ignore[arg-type]

    def test_callback_is_applied_to_keys(self):
        # Keys are lexicographically ascending ('alice' < 'bob' < 'charlie')
        # so the identity check would pass; sorting by length must FAIL
        # because lengths are 5, 3, 7 — proves the callback is applied.
        findings = PaginationFindings(
            item_keys_by_page=[["alice", "bob"], ["charlie"]]
        )
        assert_sorted_by(findings, lambda x: x)  # identity: ascending, ok
        with self.assertRaises(PaginationAuditError):
            assert_sorted_by(findings, len)  # by length: 5 > 3 violates

    def test_callback_enables_reverse_order(self):
        # By length descending: 7, 5, 3 — passes only when callback applied.
        findings = PaginationFindings(
            item_keys_by_page=[["charlie"], ["alice", "bob"]]
        )
        assert_sorted_by(findings, len, reverse=True)

    def test_callback_failure_raises(self):
        findings = PaginationFindings(item_keys_by_page=[[1, 2]])

        def _boom(_key):
            raise ValueError("nope")

        with self.assertRaises(PaginationAuditError):
            assert_sorted_by(findings, _boom)


if __name__ == "__main__":
    unittest.main()
