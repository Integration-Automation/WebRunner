import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from je_web_runner.utils.executor.action_executor import Executor
from je_web_runner.utils.observability.otel_tracing import (
    OTelTracingError,
    init_tracer,
    reset_tracer,
)


class TestOtelSoftDependency(unittest.TestCase):

    def setUp(self):
        reset_tracer()

    def tearDown(self):
        reset_tracer()

    def test_missing_otel_raises_install_hint(self):
        with patch.dict(sys.modules, {
            "opentelemetry": None,
            "opentelemetry.sdk": None,
            "opentelemetry.sdk.resources": None,
            "opentelemetry.sdk.trace": None,
            "opentelemetry.sdk.trace.export": None,
        }):
            with self.assertRaises(OTelTracingError) as ctx:
                init_tracer("svc")
            self.assertIn("opentelemetry-sdk", str(ctx.exception))


class TestExecutorSpanFactoryHook(unittest.TestCase):

    def test_factory_invoked_per_action(self):
        executor = Executor()
        captured = []

        @contextmanager
        def factory(name):
            captured.append(("enter", name))
            yield
            captured.append(("exit", name))

        executor.set_action_span_factory(factory)
        executor.event_dict["WR_test_op"] = lambda: "ok"
        result = executor._execute_with_retry(["WR_test_op"])
        self.assertEqual(result, "ok")
        self.assertEqual(captured, [("enter", "WR_test_op"), ("exit", "WR_test_op")])

    def test_no_factory_means_no_wrapping(self):
        executor = Executor()
        executor.event_dict["WR_test_op"] = lambda: "ok"
        # Should not raise even though _action_span_factory is None.
        self.assertEqual(executor._execute_with_retry(["WR_test_op"]), "ok")

    def test_factory_disabled_when_set_to_none(self):
        executor = Executor()
        invoked = []

        @contextmanager
        def factory(name):
            invoked.append(name)
            yield

        executor.set_action_span_factory(factory)
        executor.set_action_span_factory(None)
        executor.event_dict["WR_test_op"] = lambda: "ok"
        executor._execute_with_retry(["WR_test_op"])
        self.assertEqual(invoked, [])


if __name__ == "__main__":
    unittest.main()
