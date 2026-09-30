"""Facade: Email, push, OTP, webhooks, message queues and run notifications."""
from je_web_runner.utils.email_deliverability.headers import (
    EmailDeliverabilityError, HeaderMap, parse_headers, assert_spf_pass, assert_dkim_pass, assert_dmarc_pass,
    assert_list_unsubscribe, assert_no_bcc_leak,
)
from je_web_runner.utils.email_render.render import (
    EmailRenderError, CapturedEmail, ViewportProfile, RenderArtifact, load_eml_file, load_eml_dir, fetch_mailhog,
    fetch_mailpit, render_email_in_viewports, assert_subject_contains, export_summary_json,
)
from je_web_runner.utils.inbox_render_outlook.render import (
    InboxRenderOutlookError, Severity, RenderFinding, audit_outlook, audit_gmail, audit_apple_mail, audit_all,
    assert_no_errors,
)
from je_web_runner.utils.mq_assert.assertions import (
    MqAssertError, Message, Consumer, drain_topic, assert_message_published, assert_no_message, assert_idempotent,
    assert_ordered,
)
from je_web_runner.utils.notifier.webhook_notifier import (
    NotifierError, summarise_run, notify_webhook, notify_slack, notify_run_summary,
)
from je_web_runner.utils.otp_interceptor.interceptor import (
    OtpInterceptError, InterceptedMessage, OtpProvider, MailHogProvider, MailpitProvider, ImapProvider,
    WebhookSmsProvider, InMemoryProvider, extract_otp_from_text, wait_for_otp,
)
from je_web_runner.utils.push_delivery.delivery import (
    PushDeliveryError, Provider, assert_fcm_payload, assert_apns_payload, assert_collapse_intent,
)
from je_web_runner.utils.slack_digest.digest import (
    SlackDigestError, FlakeStat, RiskyPr, CostTrend, DigestInputs, build_slack_blocks, build_slack_payload,
    build_teams_card, render_plain_text,
)
from je_web_runner.utils.webhook_receiver.receiver import (
    WebhookReceiverError, ReceivedRequest, WebhookServer, assert_received_path, assert_received_with_header,
    assert_received_json_matching,
)

__all__ = [
    "EmailDeliverabilityError", "HeaderMap", "parse_headers", "assert_spf_pass", "assert_dkim_pass",
    "assert_dmarc_pass", "assert_list_unsubscribe", "assert_no_bcc_leak", "EmailRenderError", "CapturedEmail",
    "ViewportProfile", "RenderArtifact", "load_eml_file", "load_eml_dir", "fetch_mailhog", "fetch_mailpit",
    "render_email_in_viewports", "assert_subject_contains", "export_summary_json", "InboxRenderOutlookError",
    "Severity", "RenderFinding", "audit_outlook", "audit_gmail", "audit_apple_mail", "audit_all",
    "assert_no_errors", "MqAssertError", "Message", "Consumer", "drain_topic", "assert_message_published",
    "assert_no_message", "assert_idempotent", "assert_ordered", "NotifierError", "summarise_run", "notify_webhook",
    "notify_slack", "notify_run_summary", "OtpInterceptError", "InterceptedMessage", "OtpProvider",
    "MailHogProvider", "MailpitProvider", "ImapProvider", "WebhookSmsProvider", "InMemoryProvider",
    "extract_otp_from_text", "wait_for_otp", "PushDeliveryError", "Provider", "assert_fcm_payload",
    "assert_apns_payload", "assert_collapse_intent", "SlackDigestError", "FlakeStat", "RiskyPr", "CostTrend",
    "DigestInputs", "build_slack_blocks", "build_slack_payload", "build_teams_card", "render_plain_text",
    "WebhookReceiverError", "ReceivedRequest", "WebhookServer", "assert_received_path",
    "assert_received_with_header", "assert_received_json_matching",
]
