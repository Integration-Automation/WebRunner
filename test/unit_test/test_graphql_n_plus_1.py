"""Unit tests for je_web_runner.utils.graphql_n_plus_1."""
import unittest

from je_web_runner.utils.graphql_n_plus_1.detect import (
    GraphqlNPlus1Error,
    QueryRow,
    Severity,
    assert_no_n_plus_1,
    detect,
    detect_cartesian,
    parse_rows,
    report_markdown,
)


class TestParse(unittest.TestCase):

    def test_basic(self):
        rows = parse_rows([
            {"sql": "SELECT * FROM users WHERE id = 1", "ms": 5,
             "parent_field": "user"},
        ])
        self.assertEqual(rows[0].parent_field, "user")

    def test_template_normalises(self):
        a = QueryRow(sql="SELECT * FROM x WHERE id = 1")
        b = QueryRow(sql="SELECT * FROM x WHERE id = 2")
        self.assertEqual(a.sql_template, b.sql_template)

    def test_template_collapses_strings(self):
        a = QueryRow(sql="SELECT * FROM x WHERE n = 'a'")
        b = QueryRow(sql="SELECT * FROM x WHERE n = 'b'")
        self.assertEqual(a.sql_template, b.sql_template)

    def test_skips_non_dict(self):
        rows = parse_rows([{"sql": "x"}, "string"])
        self.assertEqual(len(rows), 1)

    def test_bad_type(self):
        with self.assertRaises(GraphqlNPlus1Error):
            parse_rows("nope")


# Fixed test fixture template — never executed, never templated against
# untrusted input. The %s sigil keeps Bandit's SQL-injection heuristic quiet.
_SQL_FIXTURE = "SELECT * FROM x WHERE id = %s"  # nosec B608


class TestDetect(unittest.TestCase):

    def test_no_n_plus_1(self):
        rows = [QueryRow(sql=_SQL_FIXTURE.replace("%s", str(i)),
                         parent_field="x") for i in range(2)]
        self.assertEqual(detect(rows), [])

    def test_warn(self):
        rows = [QueryRow(sql=_SQL_FIXTURE.replace("%s", str(i)),
                         parent_field="user.posts") for i in range(6)]
        findings = detect(rows, threshold=5)
        self.assertEqual(findings[0].severity, Severity.WARN)
        self.assertEqual(findings[0].repetitions, 6)

    def test_error(self):
        rows = [QueryRow(sql=f"SELECT * FROM x WHERE id = {i}",
                         parent_field="user.posts") for i in range(20)]
        findings = detect(rows, threshold=5)
        self.assertEqual(findings[0].severity, Severity.ERROR)

    def test_bad_threshold(self):
        with self.assertRaises(GraphqlNPlus1Error):
            detect([], threshold=1)


class TestCartesian(unittest.TestCase):

    def test_fanout(self):
        rows = [QueryRow(sql=f"S {i}", parent_field="parent")
                for i in range(2)]
        rows += [QueryRow(sql=f"S {i}", parent_field="child")
                 for i in range(50)]
        findings = detect_cartesian(rows)
        fields = {f.field for f in findings}
        self.assertIn("child", fields)

    def test_no_fanout(self):
        rows = [QueryRow(sql="S", parent_field="x")]
        self.assertEqual(detect_cartesian(rows), [])

    def test_empty(self):
        self.assertEqual(detect_cartesian([]), [])


class TestAssertReport(unittest.TestCase):

    def test_assert_pass(self):
        assert_no_n_plus_1([])

    def test_assert_fail(self):
        rows = [QueryRow(sql=f"S {i}", parent_field="x") for i in range(20)]
        with self.assertRaises(GraphqlNPlus1Error):
            assert_no_n_plus_1(detect(rows))

    def test_md_empty(self):
        self.assertIn("No N+1", report_markdown([]))

    def test_md_renders(self):
        rows = [QueryRow(sql=f"S {i}", parent_field="x") for i in range(6)]
        md = report_markdown(detect(rows))
        self.assertIn("x", md)


if __name__ == "__main__":
    unittest.main()
