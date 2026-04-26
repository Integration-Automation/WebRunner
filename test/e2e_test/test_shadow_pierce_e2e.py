"""E2E: shadow_pierce against a real shadow DOM page."""
import pytest

pytestmark = pytest.mark.e2e


_SHADOW_PAGE = """
<!doctype html>
<html><body>
<script>
  class ShadowHost extends HTMLElement {
    constructor() {
      super();
      const root = this.attachShadow({ mode: 'open' });
      root.innerHTML = '<button id="hidden-btn">click me</button>';
    }
  }
  customElements.define('shadow-host', ShadowHost);
  document.body.appendChild(document.createElement('shadow-host'));
</script>
</body></html>
"""


def test_find_first_walks_open_shadow_root(chrome_driver):
    from je_web_runner.utils.dom_traversal.shadow_pierce import find_first
    chrome_driver.get(f"data:text/html,{_SHADOW_PAGE}")
    el = find_first(chrome_driver, "#hidden-btn")
    assert el is not None  # nosec B101 — pytest-style


def test_find_all_returns_list(chrome_driver):
    from je_web_runner.utils.dom_traversal.shadow_pierce import find_all
    chrome_driver.get(f"data:text/html,{_SHADOW_PAGE}")
    matches = find_all(chrome_driver, "#hidden-btn")
    assert len(matches) >= 1  # nosec B101 — pytest-style
