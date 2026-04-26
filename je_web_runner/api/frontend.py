"""Façade: device emulation / geo locale / multi-tab / shadow / storybook / state diff / pom codegen / visual review."""
from je_web_runner.utils.device_emulation.presets import (
    DeviceEmulationError,
    DevicePreset,
    apply_to_chrome_options,
    available_presets,
    cdp_emulation_command,
    get_preset,
    playwright_kwargs,
    register_preset,
)
from je_web_runner.utils.dom_traversal.shadow_pierce import (
    ShadowPierceError,
    assert_pierced_visible,
    find_all,
    find_first,
)
from je_web_runner.utils.geo_locale.geo_locale import (
    GeoLocaleError,
    GeoOverride,
    apply_overrides,
    cdp_payloads,
    playwright_context_kwargs,
)
from je_web_runner.utils.multi_tab.choreographer import (
    MultiTabError,
    TabChoreographer,
    TabHandle,
)
from je_web_runner.utils.pom_codegen.codegen import (
    DiscoveredElement,
    PomCodegenError,
    discover_elements_from_html,
    render_pom_module,
)
from je_web_runner.utils.state_diff.diff import (
    BrowserStateSnapshot,
    StateChanges,
    StateDiff,
    StateDiffError,
    capture_state,
    diff_states,
)
from je_web_runner.utils.storybook.discovery import (
    StorybookError,
    StorybookStory,
    discover_stories,
    filter_stories_by_kind,
    plan_actions_for_stories,
)
from je_web_runner.utils.storybook.visual_snapshots import (
    SnapshotOutcome,
    StorybookSnapshotError,
    StorybookSnapshotReport,
    assert_no_visual_regressions,
    capture_story_snapshots,
    safe_filename,
)
from je_web_runner.utils.visual_review.review_server import (
    VisualReviewError,
    VisualReviewServer,
    accept_baseline,
    list_diffs,
    render_index,
)
from je_web_runner.utils.webauthn.virtual_authenticator import (
    VirtualAuthenticator,
    WebAuthnError,
    add_credential,
    clear_credentials,
    enable_virtual_authenticator,
    list_credentials,
    remove_virtual_authenticator,
    set_user_verified,
)

__all__ = [
    "DeviceEmulationError", "DevicePreset",
    "apply_to_chrome_options", "available_presets",
    "cdp_emulation_command", "get_preset", "playwright_kwargs",
    "register_preset",
    "ShadowPierceError",
    "assert_pierced_visible", "find_all", "find_first",
    "GeoLocaleError", "GeoOverride",
    "apply_overrides", "cdp_payloads", "playwright_context_kwargs",
    "MultiTabError", "TabChoreographer", "TabHandle",
    "DiscoveredElement", "PomCodegenError",
    "discover_elements_from_html", "render_pom_module",
    "BrowserStateSnapshot", "StateChanges", "StateDiff", "StateDiffError",
    "capture_state", "diff_states",
    "StorybookError", "StorybookStory",
    "discover_stories", "filter_stories_by_kind", "plan_actions_for_stories",
    "SnapshotOutcome", "StorybookSnapshotError", "StorybookSnapshotReport",
    "assert_no_visual_regressions", "capture_story_snapshots", "safe_filename",
    "VisualReviewError", "VisualReviewServer",
    "accept_baseline", "list_diffs", "render_index",
    "VirtualAuthenticator", "WebAuthnError",
    "add_credential", "clear_credentials",
    "enable_virtual_authenticator", "list_credentials",
    "remove_virtual_authenticator", "set_user_verified",
]
