"""E2E: smart_wait helpers against a real Chrome session via Selenium Grid."""
import pytest

pytestmark = pytest.mark.e2e


def test_install_hooks_and_fetch_idle_resolves(chrome_driver):
    """Drive a real page and confirm wait_for_fetch_idle resolves."""
    from je_web_runner.utils.smart_wait import (
        wait_for_fetch_idle,
        wait_for_spa_route_stable,
    )
    chrome_driver.get("data:text/html,<html><body><h1 id='x'>hi</h1></body></html>")
    # No outgoing fetches on this static page; should resolve immediately
    wait_for_fetch_idle(chrome_driver, quiet_for=0.05, timeout=5.0)
    wait_for_spa_route_stable(chrome_driver, quiet_for=0.05, timeout=5.0)


def test_state_diff_round_trip(chrome_driver):
    """capture_state -> set localStorage -> capture_state should diff to one add."""
    from je_web_runner.utils.state_diff import capture_state, diff_states
    chrome_driver.get("data:text/html,<html></html>")
    before = capture_state(chrome_driver)
    chrome_driver.execute_script("localStorage.setItem('e2e-key', 'value');")
    after = capture_state(chrome_driver)
    diff = diff_states(before, after)
    assert "e2e-key" in diff.local_storage.added  # nosec B101 — pytest-style
    assert diff.local_storage.added["e2e-key"] == "value"  # nosec B101


def test_memory_leak_sample_returns_int(chrome_driver):
    """sample_used_heap should return a positive int on Chrome."""
    from je_web_runner.utils.memory_leak import sample_used_heap, MemoryLeakError
    chrome_driver.get("data:text/html,<html></html>")
    try:
        size = sample_used_heap(chrome_driver)
    except MemoryLeakError:
        pytest.skip("performance.memory not available in this Chrome build")
    assert size > 0  # nosec B101 — pytest-style


def test_csp_collector_returns_empty_when_no_csp(chrome_driver):
    """No CSP on data: URL → collector returns no violations."""
    from je_web_runner.utils.csp_reporter import CspViolationCollector
    chrome_driver.get("data:text/html,<html></html>")
    collector = CspViolationCollector()
    collector.install(chrome_driver)
    violations = collector.collect(chrome_driver)
    assert violations == []  # nosec B101 — pytest-style
