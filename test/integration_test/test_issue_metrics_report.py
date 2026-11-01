"""Real offline report rendering, filtering and embedded-payload escaping in a headless browser."""
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from je_web_runner.utils.agent.browser import BrowserSession
from je_web_runner.utils.issue_worker.metrics import IssueMetrics
from je_web_runner.utils.issue_worker.store import IssueStore
from je_web_runner.utils.issue_worker.types import IssueSnapshot


def test_offline_metrics_report_filters_sources_and_never_executes_issue_text(tmp_path):
    store = IssueStore(tmp_path / "state")
    attack = '</script><script>window.injected=1</script>'
    for source, identifier, outcome in (("github", "12", "failed"), ("jira", "WR-12", "awaiting_review")):
        issue = IssueSnapshot(source, identifier, "Fixture", "Expected behavior", "https://example.test/fixture")
        store.enqueue(issue)
        data = {"started_at": time.time() - 5, "finished_at": time.time(), "reason": attack,
                "reason_code": "fixture", "triage": {"kind": "bug"}}
        store.save(issue.key, outcome, data)
        job = store.status(issue.key)[0]
        with store.lease():
            store.record_outcome(job)
    _json, html = IssueMetrics(store).write_report(tmp_path / "metrics")
    browser = BrowserSession.open("selenium")
    try:
        from pathlib import Path
        browser.driver.get(Path(html).as_uri())
        assert len(browser.driver.find_elements(By.CSS_SELECTOR, "#groups tr")) == 2
        assert browser.driver.execute_script("return window.injected") is None
        Select(browser.driver.find_element(By.ID, "source")).select_by_value("jira")
        assert len(browser.driver.find_elements(By.CSS_SELECTOR, "#groups tr")) == 1
        assert "1 delivered / 1 recorded attempts" in browser.driver.find_element(By.ID, "totals").text
        assert "not measured" in browser.driver.find_element(By.TAG_NAME, "body").text
    finally:
        browser.close()
