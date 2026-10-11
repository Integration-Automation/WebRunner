"""連線到既有瀏覽器與 persistent context / Connecting to running browsers, and persistent contexts."""
from __future__ import annotations

from typing import Any

from je_web_runner.utils.logging.loggin_instance import web_runner_logger


class _ConnectMixin:
    """Ways to start other than :meth:`launch`.

    ``connect`` reaches a Playwright browser server and opens this wrapper's own
    context there. ``connect_over_cdp`` attaches to a Chromium started with a debugging
    port and ``launch_persistent`` opens a profile directory; both adopt a context this
    wrapper did not create, so its options are fixed (settings that rebuild the context
    raise) and quitting only disconnects from, or closes, that browser.
    """

    def connect(
        self,
        ws_endpoint: str,
        browser: str = "chromium",
        context_options: dict[str, Any] | None = None,
        **connect_options: Any,
    ) -> None:
        """Connect to a Playwright browser server (``launchServer``) and open a context there."""
        web_runner_logger.info(f"playwright connect: {browser} at {ws_endpoint}")
        self._browser = self._browser_type(browser).connect(ws_endpoint, **connect_options)
        self._context_options = dict(context_options or {})
        self._context = self._open_context()
        self._reset_pages(self._context.new_page())
        self._register_session()

    def connect_over_cdp(self, endpoint_url: str, **connect_options: Any) -> None:
        """
        附加到以除錯埠啟動的 Chromium
        Attach to a Chromium started with ``--remote-debugging-port`` and adopt its first
        context and pages (the Playwright twin of ``WR_attach_to_existing_browser``).
        """
        web_runner_logger.info(f"playwright connect_over_cdp: {endpoint_url}")
        self._browser = self._browser_type("chromium").connect_over_cdp(endpoint_url, **connect_options)
        contexts = list(self._browser.contexts)
        if contexts:
            self._adopt_context(contexts[0])
        else:
            self._context = self._open_context()
            self._reset_pages(self._context.new_page())
        self._register_session()

    def launch_persistent(
        self,
        user_data_dir: str,
        browser: str = "chromium",
        headless: bool = True,
        extension_paths: list[str] | None = None,
        **context_options: Any,
    ) -> None:
        """
        以使用者資料目錄啟動，可載入擴充功能
        Launch with a persistent profile in ``user_data_dir``; ``extension_paths``
        (unpacked Chromium extensions) are loaded through ``--load-extension``. Some
        Chromium builds only run extensions with ``headless=False``.
        """
        web_runner_logger.info(f"playwright launch_persistent: {browser} with {user_data_dir}")
        args = list(context_options.pop("args", None) or [])
        if extension_paths:
            joined = ",".join(extension_paths)
            args += [f"--disable-extensions-except={joined}", f"--load-extension={joined}"]
        if args:
            context_options["args"] = args
        context = self._browser_type(browser).launch_persistent_context(
            user_data_dir, headless=headless, **context_options,
        )
        self._browser = context.browser
        self._adopt_context(context)
        self._register_session()

    def _adopt_context(self, context: Any) -> None:
        """Use a context this wrapper did not create; its options can no longer change."""
        self._context = context
        self._fixed_context = True
        context.on("page", self._track_page)
        self._reapply_context_setup(context)
        self._restart_tracing(context)
        pages = list(context.pages) or [context.new_page()]
        self._reset_pages(pages[0])
        for page in pages[1:]:
            self._track_page(page)
