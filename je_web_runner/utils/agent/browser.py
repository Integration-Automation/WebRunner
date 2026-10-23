"""Browser adapter shared by local agents and MCP; only fixed scripts are executed."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterator

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import StaleElementReferenceException

from je_web_runner.utils.agent.types import AgentAction, AgentError, http_url
from je_web_runner.utils.driver_dispatch import evaluate_expression, run_script
from je_web_runner.utils.exploratory_ai.explorer import InteractiveElement, PageObservation
from je_web_runner.utils.smart_wait.smart_wait import (
    _INSTALL_FETCH_HOOK, _INSTALL_HISTORY_HOOK,
)

_MONITOR = """(() => {
  if (window.__wrAgentErrors) return;
  window.__wrAgentErrors = [];
  window.__wrAgentNetwork = [];
  const add = message => {
    window.__wrAgentErrors.push(String(message).slice(0, 500));
    window.__wrAgentErrors = window.__wrAgentErrors.slice(-20);
  };
  window.addEventListener('error', event => add(event.message));
  window.addEventListener('unhandledrejection', event => add(event.reason));
  const originalError = console.error;
  console.error = function(...args) { add(args.join(' ')); return originalError.apply(this, args); };
  const network = (url, status) => {
    window.__wrAgentNetwork.push({url: String(url).slice(0, 1000), status});
    window.__wrAgentNetwork = window.__wrAgentNetwork.slice(-20);
  };
  const originalFetch = window.fetch;
  window.fetch = function(...args) {
    return originalFetch.apply(this, args).then(response => {
      if (response.status >= 400) network(response.url, response.status);
      return response;
    });
  };
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function(...args) {
    this.addEventListener('loadend', () => {
      if (this.status >= 400) network(this.responseURL, this.status);
    }, {once: true});
    return originalSend.apply(this, args);
  };
})()"""

_OBSERVATION = """(() => {
  const selector = element => {
    for (const name of ['data-testid', 'id', 'name']) {
      const value = element.getAttribute(name);
      if (!value) continue;
      const candidate = '[' + name + '=' + JSON.stringify(value) + ']';
      if (document.querySelectorAll(candidate).length === 1) return candidate;
    }
    const parts = [];
    for (let node = element; node && node.nodeType === 1; node = node.parentElement) {
      const siblings = node.parentElement
        ? [...node.parentElement.children].filter(x => x.tagName === node.tagName) : [];
      parts.unshift(node.tagName.toLowerCase() + ':nth-of-type(' + (siblings.indexOf(node) + 1 || 1) + ')');
    }
    return parts.join(' > ');
  };
  const visible = element => !!element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden';
  const elements = [...document.querySelectorAll('a,button,input,textarea,select,[role=button],[role=link]')]
    .filter(visible).slice(0, 150).map(element => ({
      selector: selector(element), tag: element.tagName.toLowerCase(),
      text: (element.getAttribute('aria-label') || [...(element.labels || [])].map(x => x.innerText).join(' ')
        || element.innerText || element.getAttribute('placeholder') || '').slice(0, 200),
      role: element.getAttribute('role'), is_visible: true, is_enabled: !element.disabled
    }));
  return {url: location.href, title: document.title, elements,
    text: (document.body ? document.body.innerText : '').slice(0, 8000),
    console_errors: (window.__wrAgentErrors || []).slice(-20),
    network_errors: (window.__wrAgentNetwork || []).slice(-20),
    frames: [...document.querySelectorAll('iframe')].filter(visible).slice(0, 10).map(selector)};
})()"""


class BrowserSession:
    """Operate an owned or borrowed Selenium driver / Playwright page."""

    def __init__(self, driver: Any, backend: str, owner: Any = None) -> None:
        if backend not in {"selenium", "playwright"}:
            raise AgentError("backend must be selenium or playwright")
        self.driver = driver
        self.backend = backend
        self.owner = owner
        self.timeout = 15.0

    @classmethod
    def open(cls, backend: str, headless: bool = True) -> BrowserSession:
        """Launch an isolated wrapper without changing the global browser singletons."""
        owner: Any
        if backend == "playwright":
            from je_web_runner.webdriver.playwright_wrapper import PlaywrightWrapper
            owner = PlaywrightWrapper()
            try:
                owner.launch(headless=headless)
                session = cls(owner.page, backend, owner)
                session.driver.add_init_script(_MONITOR + ";" + _INSTALL_FETCH_HOOK + _INSTALL_HISTORY_HOOK)
                return session
            except Exception:
                owner.quit()
                raise
        from je_web_runner.webdriver.webdriver_wrapper import WebDriverWrapper
        owner = WebDriverWrapper()
        owner.set_driver("chrome", options=["--headless=new"] if headless else [], install_driver=False)
        if owner.current_webdriver is None:
            raise AgentError("Selenium could not start a local browser")
        session = cls(owner.current_webdriver, backend, owner)
        try:
            session.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": _MONITOR + ";" + _INSTALL_FETCH_HOOK + _INSTALL_HISTORY_HOOK,
            })
            return session
        except Exception:
            session.close()
            raise

    def close(self) -> None:
        """Close only browsers this adapter created."""
        if self.owner is None:
            return
        if self.backend == "playwright":
            self.owner.quit()
        else:
            self.driver.quit()

    def set_timeout(self, timeout: float) -> None:
        """Bound subsequent browser operations to the remaining task budget."""
        self.timeout = max(0.001, timeout)
        if self.backend == "playwright":
            self.driver.set_default_timeout(self.timeout * 1000)
            self.driver.set_default_navigation_timeout(self.timeout * 1000)
        else:
            self.driver.implicitly_wait(0)
            self.driver.set_page_load_timeout(self.timeout)
            self.driver.set_script_timeout(self.timeout)

    @contextmanager
    def scope(self, frame: str = "") -> Iterator[Any]:
        """Enter one explicit iframe and always restore Selenium's main document."""
        if not frame:
            yield self.driver
        elif self.backend == "playwright":
            handle = self.driver.locator(frame).element_handle(timeout=self.timeout * 1000)
            content = handle.content_frame() if handle else None
            if content is None:
                raise AgentError("iframe is unavailable")
            yield content
        else:
            self.driver.switch_to.frame(self._find(self.driver, frame, self.timeout))
            try:
                yield self.driver
            finally:
                self.driver.switch_to.default_content()

    def _matches(self, scope: Any, selector: str, enabled: bool) -> list[Any]:
        if self.backend == "playwright":
            locator = scope.locator(selector)
            elements = [locator.nth(index) for index in range(locator.count())]
            return [item for item in elements if item.is_visible() and (not enabled or item.is_enabled())]
        try:
            return [item for item in scope.find_elements(By.CSS_SELECTOR, selector)
                    if item.is_displayed() and (not enabled or item.is_enabled())]
        except StaleElementReferenceException:
            # Only the read-side probe is retried. The actual click/fill is performed once.
            return []

    def _find(self, scope: Any, selector: str, timeout: float = 0, enabled: bool = True) -> Any:
        found: list[Any] = []

        def unique() -> bool:
            found[:] = self._matches(scope, selector, enabled)
            if len(found) > 1:
                raise AgentError("selector matches multiple actionable elements")
            return len(found) == 1

        # Do not use wait_until here: it deliberately catches predicate exceptions,
        # while ambiguity must fail immediately rather than eventually timing out.
        from selenium.webdriver.support.wait import WebDriverWait
        from selenium.common.exceptions import TimeoutException
        if timeout <= 0:
            if not unique():
                raise AgentError("element is missing, hidden or disabled")
        else:
            try:
                WebDriverWait(scope, timeout, poll_frequency=0.05).until(lambda _scope: unique())
            except TimeoutException as error:
                raise AgentError("element did not become actionable before timeout") from error
        return found[0]

    def observe(self, step: int = 0) -> dict[str, Any]:
        """Observe actionable main-page and iframe elements without reading input values."""
        raw = evaluate_expression(self.driver, _OBSERVATION)
        observation = PageObservation(
            url=raw["url"], title=raw["title"], step=step,
            elements=[InteractiveElement(**item) for item in raw["elements"]],
            console_errors=raw["console_errors"],
            network_errors=raw["network_errors"],
        )
        result = asdict(observation)
        result["text"] = raw["text"]
        result["frames"] = []
        for selector in raw["frames"]:
            try:
                with self.scope(selector) as scope:
                    content = evaluate_expression(scope, _OBSERVATION)
                result["frames"].append({
                    "selector": selector, "elements": content["elements"], "text": content["text"],
                })
            except Exception as error:
                result["frames"].append({"selector": selector, "error": type(error).__name__})
        return result

    def text(self, selector: str = "body", frame: str = "") -> str:
        """Read visible text from a unique element; never read a form's value attribute."""
        with self.scope(frame) as scope:
            element = self._find(scope, selector or "body", enabled=False)
            return element.inner_text() if self.backend == "playwright" else element.text

    def visible(self, selector: str, frame: str = "") -> bool:
        """Return whether a unique visible element exists, preserving ambiguity errors."""
        with self.scope(frame) as scope:
            matches = self._matches(scope, selector, enabled=False)
            if len(matches) > 1:
                raise AgentError("success selector matches multiple visible elements")
            return len(matches) == 1

    @property
    def url(self) -> str:
        """The main page URL."""
        return self.driver.url if self.backend == "playwright" else self.driver.current_url

    def perform(self, action: AgentAction) -> str | None:
        """Perform one validated operation, never automatically replaying a click or submission."""
        if action.kind == "navigate":
            target = http_url(action.value)
            if self.backend == "playwright":
                self.driver.goto(target, wait_until="domcontentloaded")
            else:
                self.driver.get(target)
            run_script(self.driver, _MONITOR)
            return None
        if action.kind == "scroll":
            amount = -600 if action.value == "up" else 600
            run_script(self.driver, "window.scrollBy(0, arguments[0]);" if self.backend == "selenium"
                       else "amount => window.scrollBy(0, amount)", amount)
            return None
        if action.kind == "done":
            return None
        with self.scope(action.frame) as scope:
            element = self._find(scope, action.selector, self.timeout, enabled=action.kind not in {"wait", "extract"})
            return self._element_action(element, action)

    def _element_action(self, element: Any, action: AgentAction) -> str | None:
        operations = {"click": element.click, "fill": lambda: self._fill(element, action.value),
                      "select": lambda: self._select(element, action.value), "check": lambda: self._check(element),
                      "wait": lambda: None}
        if action.kind == "extract":
            return element.inner_text() if self.backend == "playwright" else element.text
        operations[action.kind]()
        return None

    def _fill(self, element: Any, value: str) -> None:
        if self.backend == "playwright":
            element.fill(value)
        else:
            element.clear()
            element.send_keys(value)

    def _select(self, element: Any, value: str) -> None:
        if self.backend == "playwright":
            element.select_option(value)
        else:
            Select(element).select_by_value(value)

    def _check(self, element: Any) -> None:
        if self.backend == "playwright":
            element.check()
        elif not element.is_selected():
            element.click()

    def screenshot(self, path: Path, secrets: set[str] | None = None) -> None:
        """Write a failure screenshot with form controls masked, restoring the page afterward."""
        mask_body = """
          const targets = [...document.querySelectorAll('input,textarea,iframe,[data-secret]')];
          for (const element of document.querySelectorAll('body *')) {
            if (element.shadowRoot || (!element.children.length
                && values.some(value => value && element.textContent.includes(value)))) {
              targets.push(element);
            }
          }
          window.__wrAgentMasks = [...new Set(targets)]
            .map(element => [element, element.style.cssText]);
          for (const [element] of window.__wrAgentMasks) element.style.setProperty('visibility', 'hidden', 'important');
        """
        restore = """(() => {
          for (const [element, style] of window.__wrAgentMasks || []) element.style.cssText = style;
          delete window.__wrAgentMasks;
        })()"""
        mask = ("const values = arguments[0];" + mask_body if self.backend == "selenium"
                else "values => {" + mask_body + "}")
        run_script(self.driver, mask, list(secrets or ()))
        try:
            if self.backend == "playwright":
                self.driver.screenshot(path=str(path), full_page=True)
            elif not self.driver.save_screenshot(str(path)):
                raise AgentError("browser did not save the failure screenshot")
        finally:
            run_script(self.driver, restore)
