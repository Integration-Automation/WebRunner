import unittest
from unittest.mock import MagicMock

from je_web_runner.utils.observability.otlp_exporter import (
    OtlpExportConfig,
    OtlpExporterError,
    build_exporter,
    configure_otlp_export,
)


class TestOtlpExportConfig(unittest.TestCase):

    def test_defaults_grpc(self):
        config = OtlpExportConfig(endpoint="https://otlp.example:4317")
        self.assertEqual(config.protocol, "grpc")
        self.assertEqual(config.timeout, 10.0)

    def test_invalid_endpoint(self):
        with self.assertRaises(OtlpExporterError):
            OtlpExportConfig(endpoint="")

    def test_invalid_protocol(self):
        with self.assertRaises(OtlpExporterError):
            OtlpExportConfig(endpoint="x", protocol="websocket")

    def test_invalid_timeout(self):
        with self.assertRaises(OtlpExporterError):
            OtlpExportConfig(endpoint="x", timeout=0)


class TestConfigureOtlpExport(unittest.TestCase):

    def test_registers_processor_with_provider(self):
        provider = MagicMock()
        provider.add_span_processor = MagicMock()
        config = OtlpExportConfig(endpoint="https://x:4317")

        fake_processor_cls = MagicMock()
        fake_exporter = MagicMock(name="exporter")

        result = configure_otlp_export(
            provider,
            config,
            processor_factory=fake_processor_cls,
            exporter_factory=lambda _config: fake_exporter,
        )
        provider.add_span_processor.assert_called_once_with(result)
        fake_processor_cls.assert_called_once_with(fake_exporter)

    def test_invalid_provider(self):
        with self.assertRaises(OtlpExporterError):
            configure_otlp_export(
                object(),
                OtlpExportConfig(endpoint="x"),
                processor_factory=MagicMock(),
                exporter_factory=lambda _c: MagicMock(),
            )


class TestBuildExporter(unittest.TestCase):
    """Ensure build_exporter raises a clear error when the SDK is missing.

    These tests do NOT import the actual OTel SDK; they monkey-patch the
    helper imports so the test stays hermetic.
    """

    def test_grpc_missing_dep_raises(self):
        from je_web_runner.utils.observability import otlp_exporter

        def _raise_missing() -> None:
            raise OtlpExporterError("missing")

        original = otlp_exporter._import_grpc_exporter
        otlp_exporter._import_grpc_exporter = _raise_missing
        try:
            with self.assertRaises(OtlpExporterError):
                build_exporter(OtlpExportConfig(endpoint="x"))
        finally:
            otlp_exporter._import_grpc_exporter = original

    def test_http_missing_dep_raises(self):
        from je_web_runner.utils.observability import otlp_exporter

        def _raise_missing() -> None:
            raise OtlpExporterError("missing")

        original = otlp_exporter._import_http_exporter
        otlp_exporter._import_http_exporter = _raise_missing
        try:
            with self.assertRaises(OtlpExporterError):
                build_exporter(OtlpExportConfig(endpoint="x", protocol="http"))
        finally:
            otlp_exporter._import_http_exporter = original


if __name__ == "__main__":
    unittest.main()
