"""
不需要瀏覽器的 MCP 工具 / The MCP tools that work offline, without a browser.

Each handler imports its WebRunner module lazily, so listing the tools stays cheap.
"""
from __future__ import annotations

from typing import Any

from je_web_runner.mcp_server._policy import checked_path
from je_web_runner.mcp_server._types import READ_ONLY, McpServerError, Tool

# Reused error messages — extracted so SonarCloud S1192 stays quiet and
# downstream tooling can grep for them.
_ERR_ACTIONS_LIST = "'actions' must be a list"
_ERR_TEXT_STRING = "'text' must be a string"


def _tool_lint_action(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.action_linter import lint_action
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    # ``lint_action`` returns ``List[Dict[str, Any]]`` with ``rule`` /
    # ``severity`` / ``message`` / ``location`` keys; pass through verbatim
    # so MCP clients see the same shape the Python API exposes.
    return list(lint_action(actions))


def _tool_locator_strength(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.locator_strength import score_locator
    score = score_locator(
        str(arguments.get("strategy", "")),
        str(arguments.get("value", "")),
    )
    return {
        "strategy": score.strategy,
        "value": score.value,
        "score": score.score,
        "reasons": score.reasons,
    }


def _tool_render_template(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.action_templates.templates import render_template
    return render_template(
        str(arguments.get("template", "")),
        arguments.get("parameters") or {},
    )


def _tool_compute_trend(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.trend_dashboard.trend import compute_trend
    return compute_trend(checked_path(str(arguments.get("ledger_path", ""))))


def _tool_validate_response(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.contract_testing.contract import validate_response
    body = arguments.get("body")
    schema = arguments.get("schema")
    if not isinstance(schema, dict):
        raise McpServerError("'schema' must be an object")
    result = validate_response(body, schema)
    return {"valid": result.valid, "errors": result.errors}


def _tool_summary_markdown(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.pr_comment.poster import (
        PrSummary,
        build_summary_markdown,
    )
    summary = PrSummary(
        total=int(arguments.get("total", 0)),
        passed=int(arguments.get("passed", 0)),
        failed=int(arguments.get("failed", 0)),
        skipped=int(arguments.get("skipped", 0)),
        flaky=int(arguments.get("flaky", 0)),
        duration_seconds=arguments.get("duration_seconds"),
    )
    return build_summary_markdown(summary, run_url=arguments.get("run_url"))


def _tool_diff_shard(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sharding.diff_shard import select_action_files
    candidates = arguments.get("candidates") or []
    changed = arguments.get("changed") or []
    return select_action_files(list(candidates), list(changed))


def _tool_render_k8s(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.k8s_runner.manifest import (
        ShardJobConfig,
        render_job_manifests,
    )
    config = ShardJobConfig(
        name_prefix=str(arguments.get("name_prefix", "webrunner")),
        image=str(arguments.get("image", "")),
        total_shards=int(arguments.get("total_shards", 1)),
        actions_dir=str(arguments.get("actions_dir", "")),
    )
    return render_job_manifests(config)


def _tool_partition(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sharding.shard import partition
    return partition(
        list(arguments.get("paths") or []),
        int(arguments.get("index", 1)),
        int(arguments.get("total", 1)),
    )


def _tool_format_actions(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.action_formatter.formatter import format_actions
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    return format_actions(actions, indent=int(arguments.get("indent", 2)))


def _tool_parse_markdown(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.md_authoring.markdown_to_actions import parse_markdown
    text = arguments.get("text")
    if not isinstance(text, str):
        raise McpServerError(_ERR_TEXT_STRING)
    return parse_markdown(text)


def _tool_translate_actions_to_playwright(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sel_to_pw.translator import translate_action_list
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    return translate_action_list(actions)


def _tool_translate_python_to_playwright(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.sel_to_pw.translator import translate_python_source
    source = arguments.get("source")
    if not isinstance(source, str):
        raise McpServerError("'source' must be a string")
    translations = translate_python_source(source)
    return [
        {"line": t.line, "original": t.original,
         "translated": t.translated, "note": t.note}
        for t in translations
    ]


def _tool_pom_from_html(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.pom_codegen.codegen import (
        discover_elements_from_html,
        render_pom_module,
    )
    html = arguments.get("html")
    if not isinstance(html, str):
        raise McpServerError("'html' must be a string")
    elements = discover_elements_from_html(html)
    class_name = str(arguments.get("class_name", "WebRunnerPage"))
    return {
        "module": render_pom_module(elements, class_name=class_name),
        "elements": [
            {"name": e.name, "strategy": e.strategy,
             "value": e.value, "tag": e.tag, "source": e.source}
            for e in elements
        ],
    }


def _tool_scan_pii(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.pii_scanner.scanner import scan_text
    text = arguments.get("text")
    if not isinstance(text, str):
        raise McpServerError(_ERR_TEXT_STRING)
    categories = arguments.get("categories")
    findings = scan_text(text, categories=categories)
    return [
        {"category": f.category, "start": f.start,
         "end": f.end, "redacted": f.redacted}
        for f in findings
    ]


def _tool_redact_pii(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.pii_scanner.scanner import redact_text
    text = arguments.get("text")
    if not isinstance(text, str):
        raise McpServerError(_ERR_TEXT_STRING)
    return redact_text(
        text,
        replacement=str(arguments.get("replacement", "[REDACTED]")),
        categories=arguments.get("categories"),
    )


def _tool_cluster_failures(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.failure_cluster.clustering import (
        cluster_failures,
        cluster_summary,
    )
    failures = arguments.get("failures")
    if not isinstance(failures, list):
        raise McpServerError("'failures' must be a list")
    top_n = arguments.get("top_n")
    if top_n is not None:
        top_n = int(top_n)
    clusters = cluster_failures(failures, top_n=top_n)
    return cluster_summary(clusters)


def _tool_a11y_diff(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.accessibility.a11y_diff import diff_violations
    baseline = arguments.get("baseline")
    current = arguments.get("current")
    if not isinstance(baseline, list) or not isinstance(current, list):
        raise McpServerError("'baseline' and 'current' must be lists")
    diff = diff_violations(baseline, current)
    return {
        "added": diff.added,
        "resolved": diff.resolved,
        "persisting": diff.persisting,
        "regressed": diff.regressed,
    }


def _tool_score_action_locators(arguments: dict[str, Any]) -> Any:
    from je_web_runner.utils.linter.locator_strength import score_action_locators
    actions = arguments.get("actions")
    if not isinstance(actions, list):
        raise McpServerError(_ERR_ACTIONS_LIST)
    return list(score_action_locators(actions))


def _args(required: tuple[str, ...], **properties: dict[str, Any]) -> dict[str, Any]:
    """A closed ``object`` input schema: unknown arguments are rejected."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def _arg(json_type: str | None, description: str, **extra: Any) -> dict[str, Any]:
    """One described property; ``json_type=None`` accepts any JSON value."""
    spec: dict[str, Any] = {"description": description, **extra}
    if json_type:
        spec["type"] = json_type
    return spec


_ACTIONS = _arg("array", "WebRunner action list: [command_name, params] entries.", items={"type": "array"})
_TEXT = _arg("string", "The text to scan.")
_PII_CATEGORIES = _arg(
    "array", "Limit to these categories: email, phone_e164, credit_card, ssn_us, taiwan_id, ipv4.",
    items={"type": "string"},
)


def build_default_tools() -> list[Tool]:
    """Construct the default tool list shipped with the server."""
    return [
        Tool(
            name="webrunner_lint_action",
            title="Lint an action list",
            description="Lint a WebRunner action JSON list and report issues.",
            input_schema=_args(("actions",), actions=_ACTIONS),
            handler=_tool_lint_action,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_locator_strength",
            title="Score a locator",
            description="Score a (strategy, value) locator on a 0-100 scale.",
            input_schema=_args(
                ("strategy", "value"),
                strategy=_arg("string", "Locator strategy, e.g. ID, CSS_SELECTOR, XPATH, NAME."),
                value=_arg("string", "The locator value."),
            ),
            handler=_tool_locator_strength,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_render_template",
            title="Render an action template",
            description="Render a built-in or registered action template.",
            input_schema=_args(
                ("template",),
                template=_arg("string", "Template name."),
                parameters=_arg("object", "Values for the template's placeholders."),
            ),
            handler=_tool_render_template,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_compute_trend",
            title="Compute a pass-rate trend",
            description="Compute pass-rate / duration trend from a ledger file.",
            input_schema=_args(("ledger_path",), ledger_path=_arg("string", "Path of the run ledger JSON file.")),
            handler=_tool_compute_trend,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_validate_response",
            title="Validate JSON against a schema",
            description="Validate a JSON value against a minimal JSON-Schema.",
            input_schema=_args(
                ("schema",),
                body=_arg(None, "The JSON value to check."),
                schema=_arg("object", "The JSON Schema subset to check it against."),
            ),
            handler=_tool_validate_response,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_summary_markdown",
            title="Write a run summary",
            description="Build a WebRunner PR summary in Markdown.",
            input_schema=_args(
                ("total", "passed", "failed"),
                total=_arg("integer", "Number of tests run."),
                passed=_arg("integer", "Number that passed."),
                failed=_arg("integer", "Number that failed."),
                skipped=_arg("integer", "Number skipped."),
                flaky=_arg("integer", "Number that passed only on retry."),
                duration_seconds=_arg("number", "Wall-clock duration of the run."),
                run_url=_arg("string", "Link to the CI run."),
            ),
            handler=_tool_summary_markdown,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_diff_shard",
            title="Pick changed action files",
            description="Pick changed action files from a candidate / changed list.",
            input_schema=_args(
                ("candidates", "changed"),
                candidates=_arg("array", "All action file paths.", items={"type": "string"}),
                changed=_arg("array", "Paths changed in this diff.", items={"type": "string"}),
            ),
            handler=_tool_diff_shard,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_render_k8s",
            title="Render Kubernetes shard jobs",
            description="Render Kubernetes Job manifests for shard parallelism.",
            input_schema=_args(
                ("name_prefix", "image", "total_shards", "actions_dir"),
                name_prefix=_arg("string", "Prefix for the Job names."),
                image=_arg("string", "Container image that runs WebRunner."),
                total_shards=_arg("integer", "Number of shards (one Job each)."),
                actions_dir=_arg("string", "Directory of action files inside the image."),
            ),
            handler=_tool_render_k8s,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_partition_shard",
            title="Partition files into a shard",
            description="Deterministic file partitioning for shard runs (SHA-1 mod N).",
            input_schema=_args(
                ("paths", "index", "total"),
                paths=_arg("array", "File paths to partition.", items={"type": "string"}),
                index=_arg("integer", "This shard's number, starting at 1."),
                total=_arg("integer", "Total number of shards."),
            ),
            handler=_tool_partition,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_format_actions",
            title="Format an action list",
            description="Format an action JSON list with canonical kwarg order.",
            input_schema=_args(
                ("actions",),
                actions=_ACTIONS,
                indent=_arg("integer", "JSON indent width (default 2)."),
            ),
            handler=_tool_format_actions,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_parse_markdown",
            title="Turn Markdown steps into actions",
            description="Transpile a Markdown bullet list into a WR_* action list.",
            input_schema=_args(("text",), text=_arg("string", "Markdown bullet list, one step per bullet.")),
            handler=_tool_parse_markdown,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_translate_actions_to_playwright",
            title="Translate actions to Playwright",
            description=(
                "Rewrite a WR_* action list to its WR_pw_* Playwright"
                " equivalent (drops WR_implicitly_wait)."
            ),
            input_schema=_args(("actions",), actions=_ACTIONS),
            handler=_tool_translate_actions_to_playwright,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_translate_python_to_playwright",
            title="Translate Selenium Python to Playwright",
            description=(
                "Static translator: rewrites Selenium-style Python source"
                " into Playwright equivalents; returns per-line diffs."
            ),
            input_schema=_args(("source",), source=_arg("string", "Python source using Selenium.")),
            handler=_tool_translate_python_to_playwright,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_pom_from_html",
            title="Generate a page object",
            description=(
                "Discover [data-testid] / id / form fields in HTML and"
                " render a Python Page Object module."
            ),
            input_schema=_args(
                ("html",),
                html=_arg("string", "The page's HTML."),
                class_name=_arg("string", "Name of the generated class (default WebRunnerPage)."),
            ),
            handler=_tool_pom_from_html,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_scan_pii",
            title="Find personal data in text",
            description=(
                "Scan text for PII (email / phone / Luhn-card / SSN /"
                " ROC ID / IPv4); returns category + redacted preview."
            ),
            input_schema=_args(("text",), text=_TEXT, categories=_PII_CATEGORIES),
            handler=_tool_scan_pii,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_redact_pii",
            title="Redact personal data in text",
            description="Replace each detected PII match with a sentinel string.",
            input_schema=_args(
                ("text",),
                text=_arg("string", "The text to redact."),
                replacement=_arg("string", "What to put in place of each match (default [REDACTED])."),
                categories=_PII_CATEGORIES,
            ),
            handler=_tool_redact_pii,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_cluster_failures",
            title="Group failures by cause",
            description=(
                "Group failures by normalised error signature; returns"
                " top buckets sorted by count."
            ),
            input_schema=_args(
                ("failures",),
                failures=_arg("array", "Failure records, each with an error message."),
                top_n=_arg("integer", "Return only the largest N groups."),
            ),
            handler=_tool_cluster_failures,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_a11y_diff",
            title="Compare accessibility findings",
            description=(
                "Diff two axe-core ``violations`` arrays and bucket the"
                " findings into added / resolved / persisting."
            ),
            input_schema=_args(
                ("baseline", "current"),
                baseline=_arg("array", "axe-core violations from the earlier run."),
                current=_arg("array", "axe-core violations from this run."),
            ),
            handler=_tool_a11y_diff,
            annotations=READ_ONLY,
        ),
        Tool(
            name="webrunner_score_action_locators",
            title="Score an action list's locators",
            description=(
                "Score every locator referenced by an action JSON list on"
                " a 0–100 scale; lower = more fragile."
            ),
            input_schema=_args(("actions",), actions=_ACTIONS),
            handler=_tool_score_action_locators,
            annotations=READ_ONLY,
        ),
    ]
