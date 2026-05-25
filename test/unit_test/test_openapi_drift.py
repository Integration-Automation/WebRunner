"""Unit tests for je_web_runner.utils.openapi_drift."""
import unittest

from je_web_runner.utils.openapi_drift.drift import (
    ApiObservation,
    DriftReport,
    OpenapiDriftError,
    assert_no_undocumented,
    assert_no_zombies,
    diff,
)


SPEC = {
    "paths": {
        "/users": {
            "get": {"responses": {"200": {}}},
            "post": {"responses": {"201": {}, "400": {}}},
        },
        "/users/{id}": {
            "get": {"responses": {"200": {}, "404": {}}},
        },
        "/legacy": {
            "get": {"responses": {"200": {}}},
        },
    },
}


class TestDiff(unittest.TestCase):

    def test_documented_traffic_clean(self):
        report = diff(SPEC, [
            ApiObservation(method="GET", path="/users", status_code=200),
            ApiObservation(method="POST", path="/users", status_code=201),
            ApiObservation(method="GET", path="/users/42", status_code=200),
        ])
        self.assertEqual(report.undocumented, [])

    def test_undocumented_path(self):
        report = diff(SPEC, [
            ApiObservation(method="GET", path="/admin", status_code=200),
        ])
        self.assertIn("GET /admin", report.undocumented)

    def test_undocumented_method(self):
        report = diff(SPEC, [
            ApiObservation(method="DELETE", path="/users", status_code=204),
        ])
        self.assertIn("DELETE /users", report.undocumented_methods)

    def test_zombie(self):
        report = diff(SPEC, [
            ApiObservation(method="GET", path="/users", status_code=200),
        ])
        self.assertIn("GET /legacy", report.zombie)

    def test_undocumented_status(self):
        report = diff(SPEC, [
            ApiObservation(method="GET", path="/users", status_code=500),
        ])
        self.assertIn("GET /users → 500", report.undocumented_statuses)

    def test_path_param_normalises(self):
        report = diff(SPEC, [
            ApiObservation(method="GET", path="/users/abc-123", status_code=404),
        ])
        self.assertEqual(report.undocumented, [])

    def test_bad_spec(self):
        with self.assertRaises(OpenapiDriftError):
            diff("nope", [])

    def test_bad_obs(self):
        with self.assertRaises(OpenapiDriftError):
            diff(SPEC, ["nope"])


class TestAssertUndocumented(unittest.TestCase):

    def test_pass(self):
        assert_no_undocumented(DriftReport())

    def test_fail(self):
        with self.assertRaises(OpenapiDriftError):
            assert_no_undocumented(DriftReport(undocumented=["GET /x"]))


class TestAssertZombies(unittest.TestCase):

    def test_pass(self):
        assert_no_zombies(DriftReport())

    def test_threshold(self):
        assert_no_zombies(DriftReport(zombie=["x"]), max_zombies=1)

    def test_fail(self):
        with self.assertRaises(OpenapiDriftError):
            assert_no_zombies(DriftReport(zombie=["x", "y"]), max_zombies=1)

    def test_bad_max(self):
        with self.assertRaises(OpenapiDriftError):
            assert_no_zombies(DriftReport(), max_zombies=-1)


if __name__ == "__main__":
    unittest.main()
