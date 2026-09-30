"""Facade: Authoring and review tools: recorder, schema, command docs, POM, session replay, dashboards."""
from je_web_runner.utils.ci_annotations.github_annotations import (
    AnnotationError, format_error_annotation, emit_failure_annotations, emit_from_junit_xml,
)
from je_web_runner.utils.dashboard.live_dashboard import (
    DashboardError, LiveDashboard, start_dashboard, stop_dashboard,
)
from je_web_runner.utils.docs.command_reference import (
    DocsExportError, build_command_reference, export_command_reference, list_commands,
)
from je_web_runner.utils.live_dashboard.server import (
    DashboardServer,
)
from je_web_runner.utils.pom_generator.pom_generator import (
    POMGeneratorError, extract_elements_from_html, generate_pom_class, generate_pom_from_html,
    generate_pom_from_url, write_pom_to_file,
)
from je_web_runner.utils.recorder.browser_recorder import (
    RecorderError, PlaywrightScriptRunner, mask_sensitive_events, start_recording, pull_events, stop_recording,
    events_to_actions, save_recording,
)
from je_web_runner.utils.replay_studio.replay_studio import (
    ReplayStudioError, build_replay_html, export_replay_studio,
)
from je_web_runner.utils.schema.action_schema import (
    SchemaExportError, build_action_schema, export_schema,
)
from je_web_runner.utils.session_to_test.converter import (
    SessionToTestError, ConversionStats, ConversionResult, convert_rrweb_events, convert_generic_events,
    convert_events, write_actions_json,
)

__all__ = [
    "AnnotationError", "format_error_annotation", "emit_failure_annotations", "emit_from_junit_xml",
    "DashboardError", "LiveDashboard", "start_dashboard", "stop_dashboard", "DocsExportError",
    "build_command_reference", "export_command_reference", "list_commands", "DashboardServer", "POMGeneratorError",
    "extract_elements_from_html", "generate_pom_class", "generate_pom_from_html", "generate_pom_from_url",
    "write_pom_to_file", "RecorderError", "PlaywrightScriptRunner", "mask_sensitive_events", "start_recording",
    "pull_events", "stop_recording", "events_to_actions", "save_recording", "ReplayStudioError",
    "build_replay_html", "export_replay_studio", "SchemaExportError", "build_action_schema", "export_schema",
    "SessionToTestError", "ConversionStats", "ConversionResult", "convert_rrweb_events", "convert_generic_events",
    "convert_events", "write_actions_json",
]
