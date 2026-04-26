import json
import tempfile
import unittest
from pathlib import Path

from je_web_runner.utils.pipeline import (
    Pipeline,
    PipelineError,
    PipelineStage,
    load_pipeline,
)
from je_web_runner.utils.pipeline.pipeline import (
    assert_all_passed,
    run_pipeline,
)


def _runner_returning_status(map_):
    def runner(path):
        return map_.get(path, {"status": "passed"})
    return runner


def _expand_each(_pattern):
    return [_pattern]


class TestLoadPipeline(unittest.TestCase):

    def test_loads_dict(self):
        document = {"stages": [
            {"name": "lint", "files": ["a.json"]},
            {"name": "smoke", "files": ["b.json"], "required_status": ["passed"]},
        ]}
        pipeline = load_pipeline(document)
        self.assertEqual([s.name for s in pipeline.stages], ["lint", "smoke"])

    def test_loads_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pipeline.json"
            path.write_text(json.dumps({"stages": [
                {"name": "x", "files": ["a"]},
            ]}), encoding="utf-8")
            pipeline = load_pipeline(path)
            self.assertEqual(pipeline.stages[0].name, "x")

    def test_invalid_json(self):
        with self.assertRaises(PipelineError):
            load_pipeline("not json")

    def test_duplicate_stage(self):
        with self.assertRaises(PipelineError):
            load_pipeline({"stages": [
                {"name": "a", "files": []},
                {"name": "a", "files": []},
            ]})

    def test_empty_stages(self):
        with self.assertRaises(PipelineError):
            load_pipeline({"stages": []})

    def test_missing_files_key(self):
        with self.assertRaises(PipelineError):
            load_pipeline({"stages": [{"name": "x"}]})


class TestRunPipeline(unittest.TestCase):

    def test_all_pass(self):
        pipeline = Pipeline(stages=[
            PipelineStage(name="smoke", files=["a.json", "b.json"]),
        ])
        results = run_pipeline(
            pipeline,
            runner=_runner_returning_status({}),
            file_resolver=_expand_each,
        )
        self.assertEqual(results[0].status, "passed")
        self.assertEqual(len(results[0].file_results), 2)

    def test_short_circuit_on_failure(self):
        pipeline = Pipeline(stages=[
            PipelineStage(name="smoke", files=["a.json"]),
            PipelineStage(name="regression", files=["b.json"]),
        ])
        results = run_pipeline(
            pipeline,
            runner=_runner_returning_status({"a.json": {"status": "failed"}}),
            file_resolver=_expand_each,
        )
        self.assertEqual(results[0].status, "failed")
        self.assertEqual(results[1].status, "skipped")

    def test_continue_on_failure(self):
        pipeline = Pipeline(stages=[
            PipelineStage(name="lint", files=["a.json"], continue_on_failure=True),
            PipelineStage(name="smoke", files=["b.json"]),
        ])
        results = run_pipeline(
            pipeline,
            runner=_runner_returning_status({"a.json": {"status": "failed"}}),
            file_resolver=_expand_each,
        )
        self.assertEqual(results[0].status, "failed")
        # second stage still runs
        self.assertEqual(results[1].status, "passed")

    def test_runner_exception_collected(self):
        def boom(_path):
            raise RuntimeError("nope")
        pipeline = Pipeline(stages=[
            PipelineStage(name="smoke", files=["a.json"]),
        ])
        results = run_pipeline(pipeline, runner=boom, file_resolver=_expand_each)
        self.assertEqual(results[0].status, "failed")
        self.assertIn("RuntimeError", results[0].file_results[0]["error"])

    def test_invalid_pipeline(self):
        with self.assertRaises(PipelineError):
            run_pipeline("not a pipeline", lambda _: {})  # type: ignore[arg-type]

    def test_invalid_runner(self):
        with self.assertRaises(PipelineError):
            run_pipeline(Pipeline(), "not callable")  # type: ignore[arg-type]


class TestAssertAllPassed(unittest.TestCase):

    def test_passes_clean(self):
        pipeline = Pipeline(stages=[PipelineStage(name="x", files=["a"])])
        results = run_pipeline(
            pipeline,
            runner=_runner_returning_status({}),
            file_resolver=_expand_each,
        )
        assert_all_passed(results)

    def test_raises_on_failure(self):
        pipeline = Pipeline(stages=[PipelineStage(name="x", files=["a"])])
        results = run_pipeline(
            pipeline,
            runner=_runner_returning_status({"a": {"status": "failed"}}),
            file_resolver=_expand_each,
        )
        with self.assertRaises(PipelineError):
            assert_all_passed(results)


if __name__ == "__main__":
    unittest.main()
